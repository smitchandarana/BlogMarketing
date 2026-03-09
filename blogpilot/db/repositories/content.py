"""Content repository — SQLite CRUD for the content table.

Contract:
    insert(content) -> int
    get_by_id(id) -> Content | None
    get_all(status, content_type, limit) -> list[Content]
    update_status(id, status) -> None
"""

from __future__ import annotations

import logging
from blogpilot.db.connection import db_session
from blogpilot.content_engine.models.content_model import Content

logger = logging.getLogger(__name__)


def insert(content: Content, db_path: str | None = None) -> int:
    with db_session(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO content
                (insight_id, content_type, topic, title, body, file_path, hashtags, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                content.insight_id,
                content.content_type,
                content.topic,
                content.title,
                content.body,
                content.file_path,
                content.hashtags,
                content.status,
                content.created_at,
            ),
        )
        return cur.lastrowid


def get_by_id(content_id: int, db_path: str | None = None) -> Content | None:
    with db_session(db_path) as conn:
        row = conn.execute("SELECT * FROM content WHERE id = ?", (content_id,)).fetchone()
        return Content.from_row(row) if row else None


def get_all(
    status: str | None = None,
    content_type: str | None = None,
    limit: int = 100,
    db_path: str | None = None,
) -> list[Content]:
    with db_session(db_path) as conn:
        where, params = [], []
        if status:
            where.append("status = ?")
            params.append(status)
        if content_type:
            where.append("content_type = ?")
            params.append(content_type)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM content {clause} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [Content.from_row(r) for r in rows]


def update_status(content_id: int, status: str, db_path: str | None = None) -> None:
    with db_session(db_path) as conn:
        conn.execute("UPDATE content SET status = ? WHERE id = ?", (status, content_id))
