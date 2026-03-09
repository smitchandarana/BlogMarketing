"""Insight repository — SQLite CRUD for the insights table.

Contract:
    insert(insight) -> int
    get_by_id(id) -> Insight | None
    get_all(status, limit) -> list[Insight]
    update_status(id, status) -> None
    update_confidence(id, score) -> None
"""

from __future__ import annotations

import logging
from blogpilot.db.connection import db_session
from blogpilot.insight_engine.models.insight import Insight

logger = logging.getLogger(__name__)


def insert(insight: Insight, db_path: str | None = None) -> int:
    with db_session(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO insights
                (signal_ids, title, summary, category, confidence, action_items, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                insight.signal_ids_json(),
                insight.title,
                insight.summary,
                insight.category,
                insight.confidence,
                insight.action_items_json(),
                insight.status,
                insight.created_at,
            ),
        )
        return cur.lastrowid


def get_by_id(insight_id: int, db_path: str | None = None) -> Insight | None:
    with db_session(db_path) as conn:
        row = conn.execute("SELECT * FROM insights WHERE id = ?", (insight_id,)).fetchone()
        return Insight.from_row(row) if row else None


def get_all(
    status: str | None = None,
    limit: int = 100,
    db_path: str | None = None,
) -> list[Insight]:
    with db_session(db_path) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM insights WHERE status = ? ORDER BY confidence DESC, created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM insights ORDER BY confidence DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Insight.from_row(r) for r in rows]


def update_status(insight_id: int, status: str, db_path: str | None = None) -> None:
    with db_session(db_path) as conn:
        conn.execute("UPDATE insights SET status = ? WHERE id = ?", (status, insight_id))


def update_confidence(insight_id: int, confidence: float, db_path: str | None = None) -> None:
    with db_session(db_path) as conn:
        conn.execute("UPDATE insights SET confidence = ? WHERE id = ?", (confidence, insight_id))
