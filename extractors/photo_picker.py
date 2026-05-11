"""AI-powered photo picker (Groq Llama 3.2 11B Vision).

For each day's set of site photos, asks Groq to score each on:
  1. PROGRESS visibility — does it show meaningful construction work?
  2. SAFETY compliance — are visible workers wearing PPE (hat + vest)?
  3. COMPOSITION — is it suitable for a client-facing report?

Then picks the top 2 per day by a weighted score that double-weights
safety, so photos with unsafe workers never make it into the deck.

Per-day flow runs photos through a ThreadPoolExecutor (one API call per
photo), so a typical day's 5-7 photos scores in under 2 seconds.
"""
from __future__ import annotations

import base64
import json
import re
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import groq
from groq import Groq


DEFAULT_MODEL = "llama-3.2-11b-vision-preview"
DEFAULT_MAX_WORKERS = 4


SCORING_SYSTEM_PROMPT = """You are evaluating a single construction site photograph for inclusion in a Weekly Progress Report (WPR) that goes to the project's Employer and Consultant.

Rate the photograph on THREE criteria, each on an integer 0-10 scale:

1. PROGRESS — How clearly does this photograph show construction progress on site? Does it depict actual work being done, materials installed, or visible advancement?
   10 = clear shot of meaningful site work in progress
   5 = acceptable but generic
   0 = no useful construction info (e.g. just dirt, sky, or paperwork)

2. SAFETY — Are ALL visible workers wearing required PPE: a hard hat AND a high-visibility safety vest? Photos with workers missing either item will embarrass the contractor with the client.
   10 = every visible worker has both hat and vest, OR no workers are visible
   5 = mostly OK but one worker has minor PPE issue
   0 = clear safety violation — worker(s) missing hard hat or vest, or wearing improper clothing for a site

3. COMPOSITION — Is this a clean, professional shot suitable for a polished client-facing deck?
   10 = well-framed, in-focus, properly lit, shows work area clearly
   5 = acceptable but cluttered or off-axis
   0 = blurry, dark, distracting, off-topic, or shows paperwork/screens only

Return ONLY a single JSON object in this exact format. No prose, no markdown, no code fences:

{"progress": 7, "safety": 9, "composition": 8, "rationale": "Clear shot of column rebar work; workers in proper PPE"}

The rationale must be ONE short English sentence (under 20 words)."""


@dataclass
class PhotoScore:
    """Score for a single photo, plus its rationale."""

    photo_index: int          # position in the day's photo list
    progress: int = 5
    safety: int = 5
    composition: int = 5
    rationale: str = ""
    error: Optional[str] = None  # set if the scoring API call failed

    @property
    def weighted_overall(self) -> float:
        """Weighted score: safety counts double so unsafe photos rank far lower."""
        return (self.progress + 2 * self.safety + self.composition) / 4.0


def _make_client(api_key: str) -> Groq:
    return Groq(api_key=api_key)


_JSON_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _parse_score(text: str) -> tuple[int, int, int, str]:
    """Pull progress/safety/composition/rationale out of the model's reply.
    Defaults to all-5 if parsing fails (so we don't crash on a bad response)."""
    if not text:
        return 5, 5, 5, "(empty model response)"
    text = text.strip()
    # Strip optional ```json fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = _JSON_RE.search(text)
    if not match:
        return 5, 5, 5, f"(unparseable: {text[:60]})"
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return 5, 5, 5, f"(invalid JSON: {text[:60]})"

    def _clamp(v, default=5):
        try:
            return max(0, min(10, int(v)))
        except (ValueError, TypeError):
            return default

    return (
        _clamp(data.get("progress")),
        _clamp(data.get("safety")),
        _clamp(data.get("composition")),
        str(data.get("rationale", "")).strip()[:200],
    )


def score_photo(
    image_bytes: bytes,
    *,
    api_key: str,
    media_type: str = "image/jpeg",
    photo_index: int = 0,
    model: str = DEFAULT_MODEL,
    client: Optional[Groq] = None,
) -> PhotoScore:
    """Score a single photo via Groq vision."""
    if client is None:
        client = _make_client(api_key)

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=200,
            temperature=0.1,
            messages=[
                {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Rate this construction site photograph."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                        },
                    ],
                },
            ],
        )
    except groq.AuthenticationError:
        return PhotoScore(photo_index=photo_index, error="invalid Groq API key")
    except groq.RateLimitError:
        return PhotoScore(photo_index=photo_index, error="Groq rate limit")
    except groq.APIStatusError as e:
        return PhotoScore(photo_index=photo_index, error=f"Groq API error {getattr(e, 'status_code', '?')}")
    except Exception as e:  # noqa: BLE001
        return PhotoScore(photo_index=photo_index, error=f"{type(e).__name__}")

    text = (response.choices[0].message.content or "").strip()
    progress, safety, composition, rationale = _parse_score(text)
    return PhotoScore(
        photo_index=photo_index,
        progress=progress,
        safety=safety,
        composition=composition,
        rationale=rationale,
    )


def score_day_photos(
    photos: list,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_workers: int = DEFAULT_MAX_WORKERS,
    client: Optional[Groq] = None,
) -> list[PhotoScore]:
    """Score every photo in one day, in parallel. Returns one PhotoScore per photo."""
    if not photos:
        return []
    if client is None:
        client = _make_client(api_key)

    results: list[Optional[PhotoScore]] = [None] * len(photos)

    def _run(idx: int) -> PhotoScore:
        p = photos[idx]
        media = "image/png" if getattr(p, "ext", "jpg") == "png" else "image/jpeg"
        return score_photo(
            p.bytes_, api_key=api_key, media_type=media,
            photo_index=idx, model=model, client=client,
        )

    workers = max(1, min(max_workers, len(photos)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_run, i): i for i in range(len(photos))}
        for fut in as_completed(futures):
            try:
                ps = fut.result()
            except CancelledError:
                continue
            results[ps.photo_index] = ps

    # Backfill any missing slots
    for i, r in enumerate(results):
        if r is None:
            results[i] = PhotoScore(photo_index=i, error="(no result)")
    return [r for r in results if r is not None]


def pick_best_two(scores: list[PhotoScore]) -> tuple[int, int]:
    """Return (a_index, b_index) — the two highest-weighted photos.

    Safety score of 0-3 disqualifies a photo unless we have no other choice
    (so a day with all-unsafe photos still gets two picks, but a day with
    even one safe photo will never put an unsafe one in slot A or B).
    """
    if not scores:
        return (0, 0)
    if len(scores) == 1:
        return (0, 0)

    safe_enough = [s for s in scores if s.safety >= 4]
    pool = safe_enough if len(safe_enough) >= 2 else scores

    ranked = sorted(pool, key=lambda s: (-s.weighted_overall, s.photo_index))
    a = ranked[0].photo_index
    b = ranked[1].photo_index if len(ranked) > 1 else a
    return (a, b)
