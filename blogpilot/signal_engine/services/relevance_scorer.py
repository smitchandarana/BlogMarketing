"""Multi-Signal Relevance Scorer — weighted scoring across multiple factors.

Combines four scoring dimensions into a single 0.0–1.0 relevance score:
  1. Keyword match (fast, no API call)
  2. Source reputation (configurable per-source weights)
  3. Freshness decay (newer signals score higher)
  4. Semantic relevance via Groq LLM (batched for efficiency)

The final score is a weighted average of all factors. This replaces the
single-factor LLM scorer with a more robust multi-signal approach.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import datetime, timezone

from blogpilot.signal_engine.models.signal import Signal
import blogpilot.db.repositories.signals as signal_repo

logger = logging.getLogger(__name__)

# ── Weight configuration ────────────────────────────────────────────────────

_WEIGHTS = {
    "keyword": float(os.environ.get("SCORE_WEIGHT_KEYWORD", "0.25")),
    "source": float(os.environ.get("SCORE_WEIGHT_SOURCE", "0.15")),
    "freshness": float(os.environ.get("SCORE_WEIGHT_FRESHNESS", "0.10")),
    "semantic": float(os.environ.get("SCORE_WEIGHT_SEMANTIC", "0.50")),
}

# ── Keyword scoring ─────────────────────────────────────────────────────────

_NICHE_KEYWORDS = [
    # Core business terms for Phoenix Solutions
    "business intelligence", "data analytics", "power bi", "power-bi",
    "artificial intelligence", "ai", "machine learning", "ml",
    "automation", "digital transformation", "erp", "data engineering",
    "data warehouse", "cloud bi", "self-service bi", "data governance",
    "data-driven", "dashboard", "report automation", "data visualization",
    "predictive analytics", "etl", "data quality", "augmented analytics",
    # Marketing and growth
    "digital marketing", "seo", "content marketing", "social media",
    "linkedin", "lead generation", "growth", "saas", "startup",
    "web development", "web design", "e-commerce",
    # India / SMB market
    "india", "indian market", "smb", "small business", "msme",
]

_KEYWORD_PATTERNS = [re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in _NICHE_KEYWORDS]


def _keyword_score(signal: Signal) -> float:
    """Score 0.0–1.0 based on keyword density in title + summary."""
    text = f"{signal.title} {signal.summary}".lower()
    if not text.strip():
        return 0.0
    matches = sum(1 for pat in _KEYWORD_PATTERNS if pat.search(text))
    # Normalize: 0 matches = 0.0, 5+ matches = 1.0
    return min(1.0, matches / 5.0)


# ── Source reputation scoring ────────────────────────────────────────────────

_SOURCE_WEIGHTS: dict[str, float] = {
    "rss": 0.7,
    "reddit": 0.6,
    "hackernews": 0.8,
    "producthunt": 0.7,
    "github_trending": 0.75,
    "google_trends": 0.65,
    "linkedin_hashtags": 0.8,
    "news": 0.5,
    "manual": 0.9,
}


def _source_score(signal: Signal) -> float:
    """Score 0.0–1.0 based on source type reputation."""
    return _SOURCE_WEIGHTS.get(signal.source, 0.5)


# ── Freshness scoring ────────────────────────────────────────────────────────

_FRESHNESS_HALF_LIFE_HOURS = 48.0  # signals lose half their freshness score after 48h


def _freshness_score(signal: Signal) -> float:
    """Score 0.0–1.0 based on signal age using exponential decay."""
    try:
        created = datetime.fromisoformat(signal.created_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return 0.5  # unknown age — neutral

    now = datetime.now(timezone.utc)
    age_hours = max(0.0, (now - created).total_seconds() / 3600.0)
    # Exponential decay: score = 2^(-age/half_life)
    return math.pow(2.0, -age_hours / _FRESHNESS_HALF_LIFE_HOURS)


# ── Semantic scoring via Groq ────────────────────────────────────────────────

_BATCH_SIZE = 10
_SEMANTIC_PROMPT = """\
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
    """Format signals for the LLM prompt."""
    lines: list[str] = []
    for i, sig in enumerate(batch, 1):
        lines.append(f"{i}. [{sig.source}] {sig.title}")
        if sig.summary:
            lines.append(f"   {sig.summary[:200]}")
    return "\n".join(lines)


def _parse_scores(response_text: str, expected_count: int) -> list[float]:
    """Extract integer scores from model response, normalised to 0.0–1.0."""
    text = response_text.strip()
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
    logger.warning("Semantic score parse failed: %s", response_text[:200])
    return [0.5] * expected_count


def _semantic_scores(signals: list[Signal]) -> list[float]:
    """Batch-score signals via Groq for semantic relevance."""
    try:
        from llm_client import get_client  # type: ignore[import]
        client = get_client()
    except Exception as exc:
        logger.warning("Semantic scorer: LLM unavailable: %s", exc)
        return [0.5] * len(signals)

    fast_model = os.getenv("GROQ_MODEL_FAST", "llama-3.1-8b-instant")
    all_scores: list[float] = []

    for i in range(0, len(signals), _BATCH_SIZE):
        batch = signals[i: i + _BATCH_SIZE]
        prompt = _SEMANTIC_PROMPT.format(signals_text=_build_signals_text(batch))
        try:
            response = client.chat.completions.create(
                model=fast_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=128,
            )
            raw = response.choices[0].message.content or ""
            batch_scores = _parse_scores(raw, len(batch))
            all_scores.extend(batch_scores)
        except Exception as exc:
            logger.error("Semantic scoring batch %d failed: %s", i // _BATCH_SIZE + 1, exc)
            all_scores.extend([0.5] * len(batch))

    return all_scores


# ── Public API ───────────────────────────────────────────────────────────────

def score_multi(signals: list[Signal], *, db_path: str | None = None) -> list[Signal]:
    """Score signals using multi-factor weighted relevance.

    Combines keyword, source, freshness, and semantic scores into a
    single 0.0–1.0 relevance_score per signal. Persists results to DB.

    Args:
        signals: Unscored Signal objects (must have id set from DB insert).
        db_path: Optional DB path override.

    Returns:
        The same signals with relevance_score and status updated in-place.
    """
    if not signals:
        return []

    # Compute fast local scores
    kw_scores = [_keyword_score(s) for s in signals]
    src_scores = [_source_score(s) for s in signals]
    fresh_scores = [_freshness_score(s) for s in signals]

    # Compute semantic scores (batched LLM calls)
    sem_scores = _semantic_scores(signals)

    w = _WEIGHTS
    total_weight = w["keyword"] + w["source"] + w["freshness"] + w["semantic"]

    scored_count = 0
    for i, sig in enumerate(signals):
        combined = (
            w["keyword"] * kw_scores[i]
            + w["source"] * src_scores[i]
            + w["freshness"] * fresh_scores[i]
            + w["semantic"] * sem_scores[i]
        ) / total_weight

        sig.relevance_score = round(combined, 4)
        sig.status = "processed"

        if sig.id is not None:
            signal_repo.update_score(sig.id, sig.relevance_score, db_path)
        scored_count += 1

        logger.debug(
            "Signal %d scored %.3f (kw=%.2f src=%.2f fresh=%.2f sem=%.2f)",
            sig.id or 0, sig.relevance_score,
            kw_scores[i], src_scores[i], fresh_scores[i], sem_scores[i],
        )

    logger.info("Multi-scorer: scored %d/%d signals.", scored_count, len(signals))
    return signals
