"""AI-powered photo caption generator.

Calls Claude Haiku 4.5 (vision) with the photo + that day's activity list
as context. Returns one sentence in the same tone as the reference WPR
deck's photo captions.

Threading: `generate_captions_parallel` uses ThreadPoolExecutor — the
Anthropic SDK is thread-safe, so this is fine to call from a Streamlit
handler. Don't touch Streamlit state from inside worker threads; use the
progress callback to update UI from the main thread (which Streamlit calls
between thread completions).

Prompt caching: the system prompt is wrapped in `cache_control: ephemeral`.
For Haiku 4.5 the minimum cacheable prefix is 4096 tokens — this prompt is
below that, so cache won't activate today, but the marker is in place for
when the system prompt grows or the threshold changes.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import anthropic


DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_MAX_TOKENS = 200
DEFAULT_MAX_WORKERS = 5

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
    """One photo to caption.

    `activities` is the numbered "Daily Activities" list from that day's DCR
    page 2 — passed as context so Claude can tie the scene to what was
    actually being done. Empty list / None is fine.
    """
    image_bytes: bytes
    media_type: str = "image/jpeg"
    activities: Optional[list[str]] = None


def _system_blocks() -> list[dict]:
    """System prompt wrapped with cache_control for forward-compat."""
    return [
        {
            "type": "text",
            "text": CAPTION_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _user_content(req: CaptionRequest) -> list[dict]:
    image_b64 = base64.b64encode(req.image_bytes).decode("ascii")
    content: list[dict] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": req.media_type,
                "data": image_b64,
            },
        }
    ]
    if req.activities:
        listed = "\n".join(f"  {i}. {a}" for i, a in enumerate(req.activities, 1))
        content.append({
            "type": "text",
            "text": (
                "For context, the Daily Construction Report for this day lists "
                "the following site activities. Use them to inform your wording "
                "if they match what's visible in the photo — otherwise describe "
                "what you actually see and ignore them:\n\n" + listed +
                "\n\nWrite the caption."
            ),
        })
    else:
        content.append({"type": "text", "text": "Write the caption."})
    return content


def _clean_caption(text: str) -> str:
    """Trim whitespace and any stray surrounding quotation marks."""
    return text.strip().strip('"').strip("'").strip()


def generate_caption(
    req: CaptionRequest,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Generate one caption synchronously. Raises anthropic.* errors on failure."""
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_system_blocks(),
        messages=[{"role": "user", "content": _user_content(req)}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    return _clean_caption(text)


def generate_captions_parallel(
    requests: list[CaptionRequest],
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> list[str]:
    """Caption many photos in parallel. Returns a list aligned with `requests`.

    On per-photo failure: returns an error string in that slot instead of
    raising, so one bad image doesn't abort the whole batch. Cancels on
    auth errors (those repeat for every photo — no point continuing).
    """
    if not requests:
        return []

    total = len(requests)
    results: list[Optional[str]] = [None] * total
    done = 0

    if progress_cb:
        progress_cb(0, total)

    def _run(i: int, req: CaptionRequest) -> tuple[int, str, bool]:
        """Returns (index, caption, fatal). `fatal=True` means stop the batch."""
        try:
            caption = generate_caption(req, api_key=api_key, model=model)
            return i, caption, False
        except anthropic.AuthenticationError:
            return i, "(AI caption failed: invalid Anthropic API key)", True
        except anthropic.PermissionDeniedError:
            return i, "(AI caption failed: API key lacks permission)", True
        except anthropic.RateLimitError:
            return i, "(AI caption failed: rate limited — try again later)", False
        except anthropic.APIStatusError as e:
            return i, f"(AI caption failed: API error {e.status_code})", False
        except Exception as e:  # noqa: BLE001
            return i, f"(AI caption failed: {type(e).__name__})", False

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
                # Cancel remaining tasks — the same error will hit every photo
                for f in futures:
                    f.cancel()

    return [r or "(no result)" for r in results]
