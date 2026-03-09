"""Signal repository — all SQLite CRUD for the signals table.

Contract (stable interface for services to import from):
    insert(signal) -> int
    get_by_id(id) -> Signal | None
    get_all(status, limit) -> list[Signal]
    get_existing_urls() -> set[str]
    update_score(id, score) -> None
    update_status(id, status) -> None
"""

from __future__ import annotations

import logging
from blogpilot.db.connection import db_session
from blogpilot.signal_engine.models.signal import Signal

logger = logging.getLogger(__name__)


def insert(signal: Signal, db_path: str | None = None) -> int:
    """Persist a new Signal and return its DB id."""
    with db_session(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO signals
                (source, source_url, title, summary, category,
                 raw_data, relevance_score, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal.source,
                signal.source_url,
                signal.title,
                signal.summary,
                signal.category,
                signal.raw_data,
                signal.relevance_score,
                signal.status,
                signal.created_at,
            ),
        )
        return cur.lastrowid


def get_by_id(signal_id: int, db_path: str | None = None) -> Signal | None:
    """Fetch a single Signal by id."""
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM signals WHERE id = ?", (signal_id,)
        ).fetchone()
        return Signal.from_row(row) if row else None


def get_all(
    status: str | None = None,
    limit: int = 100,
    db_path: str | None = None,
) -> list[Signal]:
    """Return signals ordered by created_at DESC, optionally filtered by status."""
    with db_session(db_path) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM signals WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Signal.from_row(r) for r in rows]


def get_existing_urls(db_path: str | None = None) -> set[str]:
    """Return all known source_urls (for deduplication in collector)."""
    with db_session(db_path) as conn:
        rows = conn.execute("SELECT source_url FROM signals").fetchall()
        return {r["source_url"] for r in rows if r["source_url"]}


def update_score(
    signal_id: int,
    score: float,
    db_path: str | None = None,
) -> None:
    """Update relevance_score and mark as processed."""
    with db_session(db_path) as conn:
        conn.execute(
            "UPDATE signals SET relevance_score = ?, status = 'processed' WHERE id = ?",
            (score, signal_id),
        )


def update_status(
    signal_id: int,
    status: str,
    db_path: str | None = None,
) -> None:
    """Update the status of a signal."""
    with db_session(db_path) as conn:
        conn.execute(
            "UPDATE signals SET status = ? WHERE id = ?",
            (status, signal_id),
        )
