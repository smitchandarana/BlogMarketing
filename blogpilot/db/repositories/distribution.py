"""Repository for distribution_queue table."""

from __future__ import annotations

import logging

from blogpilot.db.connection import get_connection
from blogpilot.distribution_engine.models.distribution_queue_model import DistributionQueue

logger = logging.getLogger(__name__)


def insert(item: DistributionQueue, db_path: str | None = None) -> int:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO distribution_queue
               (content_id, channel, scheduled_at, status, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (item.content_id, item.channel, item.scheduled_time, item.status, item.created_at),
        )
        conn.commit()
        return cur.lastrowid


def get_by_id(item_id: int, db_path: str | None = None) -> DistributionQueue | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM distribution_queue WHERE id = ?", (item_id,)
        ).fetchone()
    return DistributionQueue.from_row(row) if row else None


def get_all(
    status: str | None = None,
    channel: str | None = None,
    limit: int = 50,
    db_path: str | None = None,
) -> list[DistributionQueue]:
    query = "SELECT * FROM distribution_queue WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if channel:
        query += " AND channel = ?"
        params.append(channel)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [DistributionQueue.from_row(r) for r in rows]


def get_due(db_path: str | None = None) -> list[DistributionQueue]:
    """Return queued/scheduled items whose scheduled_time has arrived."""
    query = """
        SELECT * FROM distribution_queue
        WHERE status IN ('queued', 'scheduled')
          AND (scheduled_at IS NULL OR scheduled_at <= datetime('now'))
        ORDER BY scheduled_at ASC
        LIMIT 20
    """
    with get_connection(db_path) as conn:
        rows = conn.execute(query).fetchall()
    return [DistributionQueue.from_row(r) for r in rows]


def update_status(
    item_id: int,
    status: str,
    *,
    published_at: str | None = None,
    error_message: str | None = None,
    external_url: str | None = None,
    db_path: str | None = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """UPDATE distribution_queue
               SET status = ?, published_at = ?, error_message = ?, external_url = ?
               WHERE id = ?""",
            (status, published_at, error_message, external_url, item_id),
        )
        conn.commit()


def update_scheduled_time(
    item_id: int,
    scheduled_time: str,
    db_path: str | None = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE distribution_queue SET scheduled_at = ?, status = 'scheduled' WHERE id = ?",
            (scheduled_time, item_id),
        )
        conn.commit()
