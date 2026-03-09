"""Repository for the metrics table."""

from __future__ import annotations

import json
import logging

from blogpilot.db.connection import get_connection
from blogpilot.analytics_engine.models.metrics_model import Metrics

logger = logging.getLogger(__name__)


def upsert(m: Metrics, db_path: str | None = None) -> int:
    """Insert a new metrics record (one record per collection run per content+channel)."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO metrics
               (content_id, channel, impressions, clicks, likes, comments,
                engagements, shares, engagement_score, raw_payload, measured_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                m.content_id, m.channel, m.impressions, m.clicks,
                m.likes, m.comments, m.engagements, m.shares,
                m.engagement_score, m.raw_payload, m.recorded_at,
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_by_content(
    content_id: int,
    db_path: str | None = None,
) -> list[Metrics]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM metrics WHERE content_id = ? ORDER BY measured_at DESC",
            (content_id,),
        ).fetchall()
    return [Metrics.from_row(r) for r in rows]


def get_latest_by_content(
    content_id: int,
    channel: str,
    db_path: str | None = None,
) -> Metrics | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM metrics
               WHERE content_id = ? AND channel = ?
               ORDER BY measured_at DESC LIMIT 1""",
            (content_id, channel),
        ).fetchone()
    return Metrics.from_row(row) if row else None


def get_top_by_engagement(
    channel: str | None = None,
    limit: int = 10,
    db_path: str | None = None,
) -> list[dict]:
    """Return top content_ids ranked by latest engagement_score."""
    query = """
        SELECT m.content_id, c.topic, c.content_type,
               MAX(m.engagement_score) AS best_score,
               MAX(m.impressions) AS peak_impressions
        FROM metrics m
        LEFT JOIN content c ON c.id = m.content_id
        WHERE 1=1
    """
    params: list = []
    if channel:
        query += " AND m.channel = ?"
        params.append(channel)
    query += " GROUP BY m.content_id ORDER BY best_score DESC LIMIT ?"
    params.append(limit)
    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_hourly_engagement(
    channel: str,
    db_path: str | None = None,
) -> list[dict]:
    """Return average engagement_score grouped by hour of published_at."""
    query = """
        SELECT CAST(strftime('%H', dq.published_at) AS INTEGER) AS hour,
               AVG(m.engagement_score) AS avg_engagement,
               COUNT(*) AS sample_count
        FROM metrics m
        JOIN distribution_queue dq ON dq.content_id = m.content_id
          AND dq.channel = m.channel
          AND dq.status = 'published'
        WHERE m.channel = ?
          AND dq.published_at IS NOT NULL
        GROUP BY hour
        ORDER BY avg_engagement DESC
    """
    with get_connection(db_path) as conn:
        rows = conn.execute(query, (channel,)).fetchall()
    return [dict(r) for r in rows]


def get_topic_performance(db_path: str | None = None) -> list[dict]:
    """Return topics ranked by average engagement_score across all content."""
    query = """
        SELECT c.topic,
               AVG(m.engagement_score) AS avg_engagement,
               COUNT(DISTINCT m.content_id) AS content_count
        FROM metrics m
        JOIN content c ON c.id = m.content_id
        GROUP BY c.topic
        ORDER BY avg_engagement DESC
        LIMIT 20
    """
    with get_connection(db_path) as conn:
        rows = conn.execute(query).fetchall()
    return [dict(r) for r in rows]


def get_format_performance(db_path: str | None = None) -> list[dict]:
    """Return content_type ranked by average engagement_score."""
    query = """
        SELECT c.content_type,
               AVG(m.engagement_score) AS avg_engagement,
               COUNT(DISTINCT m.content_id) AS content_count
        FROM metrics m
        JOIN content c ON c.id = m.content_id
        GROUP BY c.content_type
        ORDER BY avg_engagement DESC
    """
    with get_connection(db_path) as conn:
        rows = conn.execute(query).fetchall()
    return [dict(r) for r in rows]
