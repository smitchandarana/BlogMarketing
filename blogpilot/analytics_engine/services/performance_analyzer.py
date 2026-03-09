"""Performance Analyzer — scores content and writes feedback to shared tables.

Scoring formula:
    performance_score = (engagement_score * 0.5)
                      + (click_rate * 0.3)
                      + (recency_bonus * 0.2)

Feedback loop (no engine modification):
    - schedule_preferences table: best posting hours per channel
      → read by linkedin_publisher_service.get_next_optimal_time()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import blogpilot.db.repositories.metrics as metrics_repo
from blogpilot.db.connection import get_connection

logger = logging.getLogger(__name__)

_RECENCY_DAYS = 30   # Content published within this window gets a recency bonus


def analyze(db_path: str | None = None) -> dict:
    """Run full analysis cycle.

    Steps:
      1. Compute and persist performance_score for every content item with metrics.
      2. Update schedule_preferences with best posting hours per channel.

    Returns:
        Summary dict.
    """
    scored = _score_all_content(db_path)
    _update_schedule_preferences(db_path)
    summary = {"content_scored": scored, "timestamp": _now()}
    logger.info("Performance analysis complete: %s", summary)
    return summary


def get_dashboard(db_path: str | None = None) -> dict:
    """Return aggregated dashboard data."""
    top_topics = metrics_repo.get_topic_performance(db_path)
    top_formats = metrics_repo.get_format_performance(db_path)
    li_hours = metrics_repo.get_hourly_engagement("linkedin", db_path)
    web_hours = metrics_repo.get_hourly_engagement("website", db_path)

    avg_engagement = 0.0
    if top_topics:
        avg_engagement = round(
            sum(t["avg_engagement"] for t in top_topics) / len(top_topics), 4
        )

    return {
        "avg_engagement_rate": avg_engagement,
        "top_topics": top_topics[:10],
        "top_formats": top_formats,
        "best_linkedin_hours": li_hours[:5],
        "best_website_hours": web_hours[:5],
    }


def get_top_content(limit: int = 10, db_path: str | None = None) -> list[dict]:
    """Return top-performing content items by performance_score."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT id, topic, content_type, performance_score, status, created_at
               FROM content
               WHERE performance_score > 0
               ORDER BY performance_score DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _score_all_content(db_path: str | None = None) -> int:
    """Compute performance_score for every content item that has metrics."""
    with get_connection(db_path) as conn:
        content_ids = [
            row[0] for row in
            conn.execute("SELECT DISTINCT content_id FROM metrics").fetchall()
        ]

    scored = 0
    for cid in content_ids:
        score = _compute_score(cid, db_path)
        if score is not None:
            _persist_score(cid, score, db_path)
            scored += 1

    return scored


def _compute_score(content_id: int, db_path: str | None = None) -> float | None:
    """Compute performance_score for a single content item."""
    records = metrics_repo.get_by_content(content_id, db_path)
    if not records:
        return None

    # Use the most recent metrics record
    latest = records[0]

    engagement_score = latest.engagement_score
    click_rate = latest.clicks / max(latest.impressions, 1)
    recency_bonus = _recency_bonus(latest.recorded_at)

    score = (
        engagement_score * 0.5
        + click_rate * 0.3
        + recency_bonus * 0.2
    )
    return round(score, 6)


def _recency_bonus(recorded_at: str) -> float:
    """Returns 1.0 for very recent content, decaying to 0.0 at _RECENCY_DAYS."""
    try:
        dt = datetime.fromisoformat(recorded_at.rstrip("Z"))
        age_days = (datetime.utcnow() - dt).days
        return max(0.0, 1.0 - age_days / _RECENCY_DAYS)
    except Exception:
        return 0.0


def _persist_score(content_id: int, score: float, db_path: str | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE content SET performance_score = ? WHERE id = ?",
            (score, content_id),
        )
        conn.commit()


def _update_schedule_preferences(db_path: str | None = None) -> None:
    """Write best posting hours per channel to schedule_preferences table."""
    for channel in ("linkedin", "website"):
        hourly = metrics_repo.get_hourly_engagement(channel, db_path)
        if not hourly:
            continue
        now = _now()
        with get_connection(db_path) as conn:
            for row in hourly:
                if row["hour"] is None:
                    continue
                conn.execute(
                    """INSERT OR REPLACE INTO schedule_preferences
                       (channel, hour, avg_engagement, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (channel, int(row["hour"]), float(row["avg_engagement"]), now),
                )
            conn.commit()
    logger.info("schedule_preferences updated.")


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"
