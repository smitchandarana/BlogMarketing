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


class _ClosingConnection(sqlite3.Connection):
    """sqlite3.Connection whose context manager also closes the connection.

    Stdlib sqlite3.Connection.__exit__ only commits/rolls back the current
    transaction — it never closes the connection. Nearly every call site in
    this codebase uses ``with get_connection(...) as conn:`` expecting the
    connection to be released afterwards, which was leaking a connection
    (and file descriptor) on every call. This subclass fixes that without
    touching any call site.
    """

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


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

    conn = sqlite3.connect(db_path, factory=_ClosingConnection)
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
