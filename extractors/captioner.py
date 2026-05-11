"""AI-powered photo caption generator (Groq Llama 3.2 11B Vision).

Why Groq: their free tier is the most generous of any vision-capable LLM
API at the time of writing. Typical limits (Llama 3.2 11B Vision Preview):

    ~14,400 requests / day  (≈57× Gemini Flash's 250/day)
    ~30 requests / minute
    ~7,000 tokens / minute

Get a free key (no credit card) at https://console.groq.com.

Threading: `generate_captions_parallel` uses ThreadPoolExecutor. Groq's
RPM cap on free tier is high enough that 4 workers is comfortable for a
12-photo batch. The groq client is thread-safe.

If you ever want to A/B caption quality, swap `DEFAULT_MODEL` to
`llama-3.2-90b-vision-preview` (better quality, lower RPD ~1,000) or
the newer Llama 4 multimodal variants when stable.
"""
from __future__ import annotations

import base64
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import groq
from groq import Groq


DEFAULT_MODEL = "llama-3.2-11b-vision-preview"
DEFAULT_MAX_WORKERS = 4              # Groq free tier: ~30 RPM, 4 workers is safe
DEFAULT_INTER_REQUEST_DELAY = 0.0    # no throttle needed
DEFAULT_MAX_OUTPUT_TOKENS = 200
DEFAULT_RATE_LIMIT_RETRIES = 1
DEFAULT_RATE_LIMIT_BACKOFF = 8.0


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


def _build_user_text(req: CaptionRequest) -> str:
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


def _make_client(api_key: str) -> Groq:
    return Groq(api_key=api_key)


def generate_caption(
    req: CaptionRequest,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    client: Optional[Groq] = None,
) -> str:
    """Caption one photo synchronously via Groq."""
    if client is None:
        client = _make_client(api_key)

    image_b64 = base64.b64encode(req.image_bytes).decode("ascii")
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_output_tokens,
        temperature=0.4,
        messages=[
            {"role": "system", "content": CAPTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _build_user_text(req)},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{req.media_type};base64,{image_b64}",
                        },
                    },
                ],
            },
        ],
    )
    return _clean_caption(response.choices[0].message.content)


def _classify_429(error_text: str) -> str:
    """Pick a friendly message for Groq rate-limit / quota errors."""
    et = error_text.lower()
    if "rpd" in et or "per-day" in et or "daily" in et:
        return (
            "AI caption failed: Groq daily request limit reached. "
            "Try again tomorrow or generate a new key at console.groq.com."
        )
    if "rpm" in et or "per-minute" in et or "minute" in et:
        return "AI caption failed: Groq per-minute rate limit. Retrying…"
    return "AI caption failed: Groq rate limit (try again in a minute)"


def _is_batch_doomed_429(error_text: str) -> bool:
    """True if every other photo in the batch will hit the same 429."""
    et = error_text.lower()
    return "rpd" in et or "per-day" in et or "daily" in et


def generate_captions_parallel(
    requests: list[CaptionRequest],
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_workers: int = DEFAULT_MAX_WORKERS,
    inter_request_delay: float = DEFAULT_INTER_REQUEST_DELAY,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> list[str]:
    """Caption many photos in parallel via Groq.

    Defaults are tuned for Groq's free tier: 4 workers, no inter-request
    delay (Groq's free RPM is high enough). 12 photos typically completes
    in 5-10 seconds.
    """
    import time as _time

    if not requests:
        return []

    total = len(requests)
    results: list[Optional[str]] = [None] * total
    done = 0
    client = _make_client(api_key)

    if progress_cb:
        progress_cb(0, total)

    def _run(i: int, req: CaptionRequest) -> tuple[int, str, bool]:
        for attempt in range(DEFAULT_RATE_LIMIT_RETRIES + 1):
            try:
                caption = generate_caption(req, api_key=api_key, model=model, client=client)
                if not caption:
                    return i, "(AI caption failed: empty response)", False
                return i, caption, False
            except groq.AuthenticationError:
                return i, "(AI caption failed: invalid Groq API key)", True
            except groq.PermissionDeniedError:
                return i, "(AI caption failed: Groq API key lacks permission)", True
            except groq.RateLimitError as e:
                err_text = str(e)
                if _is_batch_doomed_429(err_text):
                    return i, f"({_classify_429(err_text)})", True
                if attempt < DEFAULT_RATE_LIMIT_RETRIES:
                    _time.sleep(DEFAULT_RATE_LIMIT_BACKOFF)
                    continue
                return i, f"({_classify_429(err_text)})", False
            except groq.APIStatusError as e:
                code = getattr(e, "status_code", None)
                if attempt < DEFAULT_RATE_LIMIT_RETRIES:
                    _time.sleep(DEFAULT_RATE_LIMIT_BACKOFF)
                    continue
                return i, f"(AI caption failed: Groq API error {code or ''})", False
            except Exception as e:  # noqa: BLE001
                return i, f"(AI caption failed: {type(e).__name__})", False
        return i, "(AI caption failed: retries exhausted)", False

    if max_workers <= 1:
        for idx, req in enumerate(requests):
            i, caption, fatal = _run(idx, req)
            results[i] = caption
            done += 1
            if progress_cb:
                progress_cb(done, total)
            if fatal:
                for j in range(idx + 1, total):
                    if results[j] is None:
                        results[j] = caption
                        done += 1
                        if progress_cb:
                            progress_cb(done, total)
                break
            if idx < total - 1 and inter_request_delay > 0:
                _time.sleep(inter_request_delay)
        return [r or "(no result)" for r in results]

    workers = max(1, min(max_workers, total))
    fatal_caption = None  # message to backfill into cancelled-slot results
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_run, i, r): i for i, r in enumerate(requests)}
        fatal_seen = False
        for fut in as_completed(futures):
            # Futures we cancelled in a previous iteration land here too —
            # calling .result() on them raises CancelledError. Skip those;
            # we backfill their slots after the loop.
            try:
                i, caption, fatal = fut.result()
            except CancelledError:
                continue
            results[i] = caption
            done += 1
            if progress_cb:
                progress_cb(done, total)
            if fatal and not fatal_seen:
                fatal_seen = True
                fatal_caption = caption
                for f in futures:
                    f.cancel()

    # Cancelled futures left empty slots — fill them with the fatal message
    # so the UI shows a clear reason for every photo instead of "(no result)".
    if fatal_caption is not None:
        for idx, r in enumerate(results):
            if r is None:
                results[idx] = fatal_caption
                done += 1
                if progress_cb:
                    progress_cb(done, total)

    return [r or "(no result)" for r in results]
