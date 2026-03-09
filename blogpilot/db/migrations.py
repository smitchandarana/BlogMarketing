"""Database migration runner for the Phoenix Marketing Intelligence Engine.

Adds new engine tables to the existing blog_marketing.db without touching
the existing `posts` table created by database.init_db().

Migration versions are tracked in the `schema_version` table.
All migrations are idempotent — safe to run multiple times.
"""

from __future__ import annotations

import logging
from blogpilot.db.connection import db_session

logger = logging.getLogger(__name__)

# Ordered list of (version, sql) tuples.
# Only append — never modify existing entries.
_MIGRATIONS: list[tuple[int, str | list]] = [
    (
        1,
        """
        -- Schema version tracking
        CREATE TABLE IF NOT EXISTS schema_version (
            version   INTEGER PRIMARY KEY,
            applied   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Raw industry signals collected from external sources
        CREATE TABLE IF NOT EXISTS signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source          TEXT NOT NULL,
            source_url      TEXT,
            title           TEXT NOT NULL,
            summary         TEXT,
            relevance_score REAL    NOT NULL DEFAULT 0.0,
            category        TEXT,
            raw_data        TEXT,
            status          TEXT    NOT NULL DEFAULT 'new',
            created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Decision intelligence insights derived from signals
        CREATE TABLE IF NOT EXISTS insights (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_ids      TEXT    NOT NULL DEFAULT '[]',
            title           TEXT    NOT NULL,
            summary         TEXT    NOT NULL,
            category        TEXT,
            confidence      REAL    NOT NULL DEFAULT 0.0,
            action_items    TEXT    NOT NULL DEFAULT '[]',
            status          TEXT    NOT NULL DEFAULT 'draft',
            created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- All generated content (blogs, LinkedIn posts, threads)
        CREATE TABLE IF NOT EXISTS content (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            insight_id      INTEGER,
            content_type    TEXT    NOT NULL,
            topic           TEXT    NOT NULL,
            title           TEXT,
            body            TEXT,
            file_path       TEXT,
            hashtags        TEXT,
            status          TEXT    NOT NULL DEFAULT 'draft',
            created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (insight_id) REFERENCES insights(id)
        );

        -- Distribution queue for scheduled and completed publish actions
        CREATE TABLE IF NOT EXISTS distribution_queue (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id      INTEGER NOT NULL,
            channel         TEXT    NOT NULL,
            scheduled_at    TEXT,
            published_at    TEXT,
            status          TEXT    NOT NULL DEFAULT 'queued',
            error_message   TEXT,
            external_url    TEXT,
            created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES content(id)
        );

        -- Performance metrics for published content
        CREATE TABLE IF NOT EXISTS metrics (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id      INTEGER NOT NULL,
            channel         TEXT    NOT NULL,
            impressions     INTEGER NOT NULL DEFAULT 0,
            clicks          INTEGER NOT NULL DEFAULT 0,
            engagements     INTEGER NOT NULL DEFAULT 0,
            shares          INTEGER NOT NULL DEFAULT 0,
            measured_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES content(id)
        );
        """,
    ),
    (
        2,
        # Migration 2: Extend metrics + content tables; add schedule_preferences.
        # ALTER TABLE ADD COLUMN is applied individually (SQLite does not support
        # multiple columns in one statement or IF NOT EXISTS on ALTER TABLE).
        [
            "ALTER TABLE metrics ADD COLUMN likes INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE metrics ADD COLUMN comments INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE metrics ADD COLUMN engagement_score REAL NOT NULL DEFAULT 0.0",
            "ALTER TABLE metrics ADD COLUMN raw_payload TEXT",
            "ALTER TABLE content ADD COLUMN performance_score REAL NOT NULL DEFAULT 0.0",
            """CREATE TABLE IF NOT EXISTS schedule_preferences (
                channel        TEXT    NOT NULL,
                hour           INTEGER NOT NULL,
                avg_engagement REAL    NOT NULL DEFAULT 0.0,
                updated_at     TEXT    NOT NULL,
                PRIMARY KEY (channel, hour)
            )""",
        ],
    ),
    (
        3,
        # Migration 3: LinkedIn Engagement Engine tables.
        [
            """CREATE TABLE IF NOT EXISTS engagement_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                post_urn        TEXT    NOT NULL,
                author_name     TEXT,
                post_text       TEXT,
                action          TEXT    NOT NULL,
                comment_text    TEXT,
                relevance_score REAL,
                viral_score     REAL,
                engaged_at      TEXT    NOT NULL,
                status          TEXT    NOT NULL DEFAULT 'done',
                error           TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS influencer_targets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT    NOT NULL,
                linkedin_url    TEXT    NOT NULL UNIQUE,
                category        TEXT,
                priority        INTEGER NOT NULL DEFAULT 3,
                last_checked    TEXT,
                active          INTEGER NOT NULL DEFAULT 1
            )""",
        ],
    ),
    (
        4,
        # Migration 4: Author metrics table for viral detection.
        # Stores rolling averages of engagement metrics per author,
        # updated after each engagement cycle.
        [
            """CREATE TABLE IF NOT EXISTS author_metrics (
                author_name     TEXT    PRIMARY KEY,
                avg_likes       REAL    NOT NULL DEFAULT 0.0,
                avg_comments    REAL    NOT NULL DEFAULT 0.0,
                avg_shares      REAL    NOT NULL DEFAULT 0.0,
                post_count      INTEGER NOT NULL DEFAULT 0,
                last_updated    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""",
            # Add likes/comments/shares columns to engagement_log for historical tracking
            "ALTER TABLE engagement_log ADD COLUMN post_likes INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE engagement_log ADD COLUMN post_comments INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE engagement_log ADD COLUMN post_shares INTEGER NOT NULL DEFAULT 0",
        ],
    ),
]


def _get_applied_versions(conn) -> set[int]:
    """Return the set of already-applied migration version numbers."""
    try:
        rows = conn.execute("SELECT version FROM schema_version").fetchall()
        return {row["version"] for row in rows}
    except Exception:
        # schema_version table doesn't exist yet — first run
        return set()


def run_migrations(db_path: str | None = None) -> None:
    """Apply all pending migrations to the database.

    Args:
        db_path: Optional path override. Defaults to Settings.db_path.
    """
    with db_session(db_path) as conn:
        applied = _get_applied_versions(conn)

        for version, sql in _MIGRATIONS:
            if version in applied:
                logger.debug("Migration %d already applied — skipping.", version)
                continue

            logger.info("Applying migration version %d.", version)
            statements: list[str] = (
                sql if isinstance(sql, list)
                else [s.strip() for s in sql.strip().split(";") if s.strip()]
            )
            for statement in statements:
                try:
                    conn.execute(statement)
                except Exception as exc:
                    # ALTER TABLE ADD COLUMN fails if column already exists —
                    # treat as harmless on re-run (e.g. partial migration recovery)
                    if "duplicate column" in str(exc).lower():
                        logger.debug("Column already exists (skipped): %s", exc)
                    else:
                        raise

            conn.execute(
                "INSERT OR IGNORE INTO schema_version (version) VALUES (?)", (version,)
            )
            logger.info("Migration %d applied successfully.", version)
