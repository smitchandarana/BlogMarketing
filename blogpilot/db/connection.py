"""SQLite connection factory for the Phoenix Marketing Intelligence Engine.

This is a new connection factory separate from the existing database.get_connection().
It adds WAL mode and foreign key enforcement without touching the existing module.
"""

from __future__ import annotations

import sqlite3
import logging
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode, foreign keys, and Row factory.

    Args:
        db_path: Absolute path to the .db file. Defaults to the path in Settings.

    Returns:
        An open sqlite3.Connection.
    """
    if db_path is None:
        from blogpilot.config.settings import get_settings
        db_path = get_settings().db_path

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def db_session(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that opens a connection and commits/rolls back automatically.

    Args:
        db_path: Optional path override.

    Yields:
        An open sqlite3.Connection within a transaction.
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
