"""AI-powered photo caption generator (Google Gemini 2.0 Flash).

Uses Gemini 2.0 Flash because it has the most generous free tier of any
vision-capable LLM API at the time of writing:

    1,500 requests / day
    1M input tokens / minute
    10 requests / minute (the throttle that matters for parallel batches)

Get a free key (no credit card) at https://aistudio.google.com/app/apikey.

Threading: `generate_captions_parallel` uses ThreadPoolExecutor, capped at
3 workers to stay well under the 10 RPM cap when a batch fires. The
google-genai client is thread-safe.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types


# `gemini-2.5-flash` is the current free model with vision and the widest
# project compatibility (some Google accounts have `limit: 0` quota on the
# older `gemini-2.0-flash`). Both share the same API surface.
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_MAX_WORKERS = 2  # free-tier RPM is tight — 2 workers + retry is safer than 3
DEFAULT_MAX_OUTPUT_TOKENS = 400  # 2.5-flash thinks even with budget=0 reserved a chunk
DEFAULT_RATE_LIMIT_RETRIES = 2
DEFAULT_RATE_LIMIT_BACKOFF = 6.0  # seconds — Gemini's 429s typically clear within a few


CAPTION_SYSTEM_PROMPT = """You are writing photograph captions for the Weekly Progress Report of a construction project.

PROJECT CONTEXT
- Project: Proposed B+G+4 Typical Floor + Roof Residential Building
- Location: Plot 612-9825, Ras Al Khor Industrial Area — First, Dubai, UAE
- Employer: M/S East & West International Group
- Consultant: Al Hadara Consulting & Engineering
- Main Contractor: Emirates Pearl Construction CCS Company
- Current phase: Substructure works — basement, raft foundation, columns, retaining walls, MEP first-fix
- Common elements visible in site photos: rebar mats, timber and steel formwork, concrete pumps and booms, tower crane, raft surfaces, columns and column starters, retaining walls, staircase walls, lift walls, MEP first-fix, power floats

CAPTION STYLE
Write ONE concise English sentence. 12-25 words. Match this tone EXACTLY:

- "Substructure works in progress — column reinforcement and formwork visible across raft level."
- "Lower raft column rebar and timber formwork — view from south-east."
- "Concrete pump and boom positioned for higher raft casting operation."
- "Higher raft pour in progress — concrete placement and vibration team at work."
- "Night-shift activity at the substructure works — site lighting active."
- "Cured raft surface — finishing work and surface check post-pour."
- "Rebar mat for basement slab installed across area; column starters visible."
- "Retaining-wall reinforcement and formwork prepared for next casting cycle."
- "Substructure overview — both raft levels visible with column starters."
- "Tower crane in operation — slab steel laid out across higher raft area."
- "7× power-float machines deployed for level/finish on higher raft surface."
- "Crew engaged in steel reinforcement and formwork tie-in across raft slab area."

STRUCTURE NOTES
- Captions are often a single clause, OR two clauses joined by an em-dash (—).
- The first clause names the work or element visible.
- The second clause (if present) adds a detail — location on site, equipment, view direction, or status.

RULES
- ONE English sentence only.
- 12 to 25 words. Concise.
- No emojis, no markdown, no quotation marks around the answer.
- Don't start with "This photograph shows…", "A photo of…", "The image displays…", or "Here is…".
- Don't speculate about specific worker counts, names, exact times of day, or dates not visible in the frame.
- If you're given the day's recorded site activities for context: prefer phrasing that ties the visible scene to one of those activities — but ONLY when the image clearly supports it. If the image and the activities don't match, describe the image and ignore the activities.
- If the photograph is unclear or you cannot tell what is happening, return: "Site progress photograph — substructure works area." Do not guess.

Return only the caption text. Nothing else."""


@dataclass
class CaptionRequest:
    """One photo to caption."""

    image_bytes: bytes
    media_type: str = "image/jpeg"
    activities: Optional[list[str]] = None


def _clean_caption(text: str) -> str:
    """Trim whitespace, surrounding quotes, and any leading 'Caption:' label."""
    text = (text or "").strip()
    for prefix in ("Caption:", "caption:", "CAPTION:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text.strip('"').strip("'").strip()


def _build_user_prompt(req: CaptionRequest) -> str:
    if req.activities:
        listed = "\n".join(f"  {i}. {a}" for i, a in enumerate(req.activities, 1))
        return (
            "For context, the Daily Construction Report for this day lists "
            "the following site activities. Use them to inform your wording "
            "if they match what's visible in the photo — otherwise describe "
            "what you actually see and ignore them:\n\n" + listed +
            "\n\nWrite the caption."
        )
    return "Write the caption."


def _make_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def generate_caption(
    req: CaptionRequest,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    client: Optional[genai.Client] = None,
) -> str:
    """Caption one photo synchronously."""
    if client is None:
        client = _make_client(api_key)

    contents = [
        genai_types.Part.from_bytes(data=req.image_bytes, mime_type=req.media_type),
        _build_user_prompt(req),
    ]
    # gemini-2.5-flash defaults to thinking mode, which eats the output budget
    # and truncates short captions. Disable thinking for a direct text response.
    config = genai_types.GenerateContentConfig(
        system_instruction=CAPTION_SYSTEM_PROMPT,
        max_output_tokens=max_output_tokens,
        temperature=0.4,
        thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
    )
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    return _clean_caption(response.text)


def generate_captions_parallel(
    requests: list[CaptionRequest],
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> list[str]:
    """Caption many photos in parallel. Returns a list aligned with `requests`.

    Auth / permission failures cancel the rest of the batch — the same error
    will hit every photo. Transient errors (rate limit, server error) are
    reported per-photo so a single bad image doesn't lose the whole run.
    """
    if not requests:
        return []

    total = len(requests)
    results: list[Optional[str]] = [None] * total
    done = 0
    client = _make_client(api_key)

    if progress_cb:
        progress_cb(0, total)

    def _run(i: int, req: CaptionRequest) -> tuple[int, str, bool]:
        import time as _time
        for attempt in range(DEFAULT_RATE_LIMIT_RETRIES + 1):
            try:
                caption = generate_caption(req, api_key=api_key, model=model, client=client)
                if not caption:
                    return i, "(AI caption failed: empty response)", False
                return i, caption, False
            except genai_errors.ClientError as e:
                code = getattr(e, "code", None) or getattr(e, "status_code", None)
                if code in (401, 403):
                    return i, "(AI caption failed: invalid or unauthorized Gemini API key)", True
                if code == 429 and attempt < DEFAULT_RATE_LIMIT_RETRIES:
                    _time.sleep(DEFAULT_RATE_LIMIT_BACKOFF * (attempt + 1))
                    continue
                if code == 429:
                    return i, "(AI caption failed: free-tier quota / rate limit)", False
                return i, f"(AI caption failed: client error {code or ''})", False
            except genai_errors.ServerError as e:
                code = getattr(e, "code", None) or getattr(e, "status_code", None)
                if attempt < DEFAULT_RATE_LIMIT_RETRIES:
                    _time.sleep(DEFAULT_RATE_LIMIT_BACKOFF * (attempt + 1))
                    continue
                return i, f"(AI caption failed: server error {code or ''})", False
            except Exception as e:  # noqa: BLE001
                return i, f"(AI caption failed: {type(e).__name__})", False
        return i, "(AI caption failed: retries exhausted)", False

    workers = max(1, min(max_workers, total))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_run, i, r): i for i, r in enumerate(requests)}
        fatal_seen = False
        for fut in as_completed(futures):
            i, caption, fatal = fut.result()
            results[i] = caption
            done += 1
            if progress_cb:
                progress_cb(done, total)
            if fatal and not fatal_seen:
                fatal_seen = True
                for f in futures:
                    f.cancel()

    return [r or "(no result)" for r in results]
