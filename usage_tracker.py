"""
usage_tracker.py — Daily API usage counters with hard limits.

Tracks every external API call (Groq LLM, LinkedIn posts, Unsplash fetches)
in a `usage_log` table inside blog_marketing.db, enforces per-day limits, and
tells callers how long until the daily window resets (local midnight).

Limits come from the optional `usage_limits` block in scheduler_config.json:

    "usage_limits": {
        "groq_calls_per_day": 500,
        "linkedin_posts_per_day": 3,
        "unsplash_fetches_per_day": 45
    }

Public API:
    record(service, tokens=0, success=True, detail='')
    check(service) -> bool            # True = under today's limit
    get_usage(service=None) -> dict   # today's counts + limits + remaining
    seconds_until_reset() -> int      # seconds to local midnight
    UsageLimitError                   # raised by callers when a limit is hit
"""
import json
import logging
import os
import threading
from datetime import datetime, timedelta

from database import get_connection
from paths import app_dir

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(app_dir(), 'scheduler_config.json')

_DEFAULT_LIMITS: dict[str, int] = {
    'groq': 500,        # calls/day — well under Groq free-tier RPD
    'linkedin': 3,      # posts/day — LinkedIn-safety hard cap
    'unsplash': 45,     # fetches/day — demo keys allow 50/hr; stay modest
}

_CONFIG_KEYS: dict[str, str] = {
    'groq': 'groq_calls_per_day',
    'linkedin': 'linkedin_posts_per_day',
    'unsplash': 'unsplash_fetches_per_day',
}

_table_lock = threading.Lock()
_table_ready = False


class UsageLimitError(Exception):
    """Raised when a service's daily usage limit is exhausted."""

    def __init__(self, service: str, retry_after_seconds: int) -> None:
        self.service = service
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Daily usage limit reached for '{service}' — "
            f"resets in {retry_after_seconds // 3600}h "
            f"{retry_after_seconds % 3600 // 60}m"
        )


def _ensure_table() -> None:
    global _table_ready
    if _table_ready:
        return
    with _table_lock:
        if _table_ready:
            return
        with get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS usage_log (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    service    TEXT    NOT NULL,
                    event      TEXT    NOT NULL DEFAULT 'call',
                    tokens     INTEGER NOT NULL DEFAULT 0,
                    success    INTEGER NOT NULL DEFAULT 1,
                    detail     TEXT    NOT NULL DEFAULT '',
                    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_usage_service_date '
                'ON usage_log (service, created_at)'
            )
            conn.commit()
        _table_ready = True


def get_limits() -> dict[str, int]:
    """Return per-service daily limits (config values over defaults)."""
    limits = dict(_DEFAULT_LIMITS)
    try:
        with open(_CONFIG_PATH, encoding='utf-8') as f:
            cfg = json.load(f)
        block = cfg.get('usage_limits', {}) or {}
        for service, key in _CONFIG_KEYS.items():
            if key in block:
                limits[service] = int(block[key])
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning('usage_tracker: could not read limits config: %s', exc)
    return limits


def _today_bounds() -> tuple[str, str]:
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat(sep=' '), (start + timedelta(days=1)).isoformat(sep=' ')


def record(service: str, *, tokens: int = 0, success: bool = True,
           detail: str = '', event: str = 'call') -> None:
    """Record one API usage event. Never raises."""
    try:
        _ensure_table()
        with get_connection() as conn:
            conn.execute(
                'INSERT INTO usage_log (service, event, tokens, success, detail, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (service, event, int(tokens or 0), 1 if success else 0,
                 detail[:500], datetime.now().isoformat(sep=' ')),
            )
            conn.commit()
    except Exception as exc:
        logger.warning('usage_tracker: record failed for %s: %s', service, exc)


def _count_today(service: str) -> tuple[int, int]:
    """Return (successful events today, tokens today) for a service."""
    _ensure_table()
    start, end = _today_bounds()
    with get_connection() as conn:
        row = conn.execute(
            'SELECT COUNT(*) AS n, COALESCE(SUM(tokens), 0) AS t FROM usage_log '
            'WHERE service = ? AND success = 1 AND created_at >= ? AND created_at < ?',
            (service, start, end),
        ).fetchone()
    return int(row['n']), int(row['t'])


def check(service: str) -> bool:
    """Return True when the service is under today's limit (OK to proceed)."""
    try:
        used, _ = _count_today(service)
        limit = get_limits().get(service)
        if limit is None:
            return True
        return used < limit
    except Exception as exc:
        # Fail open: a broken usage store must not halt the whole pipeline,
        # but log loudly so it gets fixed.
        logger.error('usage_tracker: check failed for %s (allowing): %s', service, exc)
        return True


def seconds_until_reset() -> int:
    """Seconds until local midnight, when daily counters reset."""
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


def get_usage(service: str | None = None) -> dict:
    """Today's usage snapshot.

    Returns:
        {"services": {name: {used, tokens, limit, remaining}},
         "resets_in_seconds": int, "date": "YYYY-MM-DD"}
        (filtered to one service when `service` is given).
    """
    limits = get_limits()
    names = [service] if service else sorted(limits)
    services: dict[str, dict] = {}
    for name in names:
        used, tokens = _count_today(name)
        limit = limits.get(name)
        services[name] = {
            'used': used,
            'tokens': tokens,
            'limit': limit,
            'remaining': max(0, limit - used) if limit is not None else None,
        }
    return {
        'services': services,
        'resets_in_seconds': seconds_until_reset(),
        'date': datetime.now().strftime('%Y-%m-%d'),
    }
