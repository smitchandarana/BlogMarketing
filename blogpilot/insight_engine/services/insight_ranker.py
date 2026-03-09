"""Insight Ranker — adjusts confidence scores based on signal quality signals.

Ranking factors (additive, normalised to 0.0–1.0):
  - Signal count      (40%): more signals → stronger trend
  - Avg relevance     (40%): avg Groq relevance_score of contributing signals
  - Recency           (20%): how recent are the signals (days old, capped at 30)

The ranker updates the confidence field on each Insight in-place and
optionally persists the updated score back to the DB.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import blogpilot.db.repositories.signals as signal_repo
import blogpilot.db.repositories.insights as insight_repo
from blogpilot.insight_engine.models.insight import Insight

logger = logging.getLogger(__name__)

_MAX_SIGNALS_FOR_FULL_SCORE = 10   # A cluster with 10+ signals gets max signal-count score
_MAX_AGE_DAYS = 30                 # Signals older than this score 0 for recency


def _recency_score(signal_created_at: str) -> float:
    """Return 1.0 for today, 0.0 for signals >= _MAX_AGE_DAYS old."""
    try:
        created = datetime.fromisoformat(signal_created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days
        return max(0.0, 1.0 - age_days / _MAX_AGE_DAYS)
    except Exception:
        return 0.5


def rank(
    insights: list[Insight],
    db_path: str | None = None,
    persist: bool = True,
) -> list[Insight]:
    """Compute final confidence scores and sort insights by priority.

    Args:
        insights: List of Insight objects (signal_ids must be populated).
        db_path:  Optional DB path override.
        persist:  If True, write updated confidence back to the insights table.

    Returns:
        Insights sorted by confidence descending.
    """
    if not insights:
        return []

    for insight in insights:
        if not insight.signal_ids:
            continue

        # Fetch contributing signals for their relevance scores and timestamps
        signals = [
            s for sid in insight.signal_ids
            if (s := signal_repo.get_by_id(sid, db_path)) is not None
        ]

        if not signals:
            continue

        # Factor 1: signal count (0.0–1.0)
        count_score = min(1.0, len(signals) / _MAX_SIGNALS_FOR_FULL_SCORE)

        # Factor 2: avg Groq relevance (already 0.0–1.0)
        avg_relevance = sum(s.relevance_score for s in signals) / len(signals)

        # Factor 3: recency (avg age of contributing signals)
        avg_recency = sum(_recency_score(s.created_at) for s in signals) / len(signals)

        # Weighted composite — blend with Groq's own confidence estimate
        composite = (
            count_score   * 0.40
            + avg_relevance * 0.40
            + avg_recency   * 0.20
        )

        # Blend with Groq-generated confidence (if set) — cap at 1.0
        blended = min(1.0, (insight.confidence + composite) / 2.0)
        insight.confidence = round(blended, 4)

        if persist and insight.id is not None:
            try:
                insight_repo.update_confidence(insight.id, insight.confidence, db_path)
            except Exception as exc:
                logger.warning("Could not persist confidence for insight %s: %s", insight.id, exc)

    # Sort: highest confidence first
    insights.sort(key=lambda i: i.confidence, reverse=True)
    logger.info("Ranker: ranked %d insights. Top confidence: %.2f", len(insights), insights[0].confidence if insights else 0)
    return insights
