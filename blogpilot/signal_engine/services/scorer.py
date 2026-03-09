"""Signal Scorer — assigns relevance scores using Groq.

Strategy:
  - Batch up to 10 signals per Groq call to minimize API usage
  - Uses llama-3.1-8b-instant (fast, cheap) not the heavy generation model
  - Prompt asks for a 0-10 integer per signal; normalised to 0.0-1.0
  - Persists scores back to DB via signal_repo.update_score()
"""

from __future__ import annotations

import json
import logging
import sys
import os

from blogpilot.signal_engine.models.signal import Signal
import blogpilot.db.repositories.signals as signal_repo

logger = logging.getLogger(__name__)

_BATCH_SIZE = 10

_SCORE_PROMPT = """\
You are a marketing intelligence analyst for Phoenix Solutions — an IT services and digital marketing agency based in India.

Rate each signal's relevance to Phoenix Solutions' business on a scale of 0-10:
- 10 = directly relevant (AI, digital marketing, web dev, SEO, social media, Indian SMB market)
- 5  = tangentially relevant (general tech, business, startups)
- 0  = irrelevant (unrelated industries, sports, entertainment)

Respond ONLY with a valid JSON array of integers matching the input order.
Example input count 3 → respond: [7, 2, 9]

Signals:
{signals_text}
"""


def _build_signals_text(batch: list[Signal]) -> str:
    lines = []
    for i, sig in enumerate(batch, 1):
        lines.append(f"{i}. [{sig.source}] {sig.title}")
        if sig.summary:
            lines.append(f"   {sig.summary[:200]}")
    return "\n".join(lines)


def _parse_scores(response_text: str, expected_count: int) -> list[float]:
    """Extract integer scores from model response, normalised to 0.0-1.0."""
    text = response_text.strip()
    # Strip markdown code fences if present
    if "```" in text:
        text = text.split("```")[1].strip()
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        scores = json.loads(text)
        if isinstance(scores, list) and len(scores) == expected_count:
            return [max(0.0, min(1.0, float(s) / 10.0)) for s in scores]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    logger.warning("Score parse failed for response: %s", response_text[:200])
    return [0.5] * expected_count  # fallback: neutral score


def score(signals: list[Signal], db_path: str | None = None) -> list[Signal]:
    """Score a list of signals using Groq and persist results.

    Args:
        signals: Unscored Signal objects (must have id set from DB insert).
        db_path: Optional DB path override.

    Returns:
        The same signals with relevance_score and status updated in-place.
    """
    if not signals:
        return []

    try:
        _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        if _ROOT not in sys.path:
            sys.path.insert(0, _ROOT)
        from llm_client import get_client, get_model  # type: ignore[import]
    except ImportError as exc:
        logger.error("Cannot import llm_client: %s", exc)
        return signals

    client = get_client()
    # Use the fast model for scoring — save the heavy model for generation
    fast_model = os.getenv("GROQ_MODEL_FAST", "llama-3.1-8b-instant")

    scored_count = 0
    for i in range(0, len(signals), _BATCH_SIZE):
        batch = signals[i : i + _BATCH_SIZE]
        signals_text = _build_signals_text(batch)
        prompt = _SCORE_PROMPT.format(signals_text=signals_text)

        try:
            response = client.chat.completions.create(
                model=fast_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=128,
            )
            raw = response.choices[0].message.content or ""
            scores = _parse_scores(raw, len(batch))

            for sig, score_val in zip(batch, scores):
                sig.relevance_score = score_val
                sig.status = "processed"
                if sig.id is not None:
                    signal_repo.update_score(sig.id, score_val, db_path)
                scored_count += 1

        except Exception as exc:
            logger.error("Scoring batch %d failed: %s", i // _BATCH_SIZE + 1, exc)
            # Leave signals with default score (0.0) — don't crash the worker

    logger.info("Scorer: scored %d/%d signals.", scored_count, len(signals))
    return signals
