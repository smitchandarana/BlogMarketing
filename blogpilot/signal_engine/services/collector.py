"""Signal Collector — orchestrates all source adapters.

Responsibilities:
  - Load signal_sources.json config
  - Instantiate and run each registered adapter
  - Deduplicate against already-stored URLs
  - Persist new signals to DB (unscored)
  - Return list of newly inserted Signal objects for the scorer

Adding a new source:
  1. Create blogpilot/signal_engine/sources/my_source.py implementing .fetch(config)
  2. Add an entry under "sources" in signal_sources.json
  3. Register the adapter class in _SOURCE_REGISTRY below
"""

from __future__ import annotations

import json
import logging
import os
import sys

from blogpilot.signal_engine.models.signal import Signal
from blogpilot.signal_engine.sources.rss import RssSource
from blogpilot.signal_engine.sources.reddit import RedditSource
from blogpilot.signal_engine.sources.hackernews import HackerNewsSource
from blogpilot.signal_engine.sources.producthunt import ProductHuntSource
from blogpilot.signal_engine.sources.github_trending import GitHubTrendingSource
from blogpilot.signal_engine.sources.google_trends import GoogleTrendsSource
from blogpilot.signal_engine.sources.linkedin_hashtags import LinkedInHashtagsSource
import blogpilot.db.repositories.signals as signal_repo

logger = logging.getLogger(__name__)

# Registry: source name → adapter class (add new adapters here)
_SOURCE_REGISTRY: dict[str, type] = {
    "rss": RssSource,
    "reddit": RedditSource,
    "hackernews": HackerNewsSource,
    "producthunt": ProductHuntSource,
    "github_trending": GitHubTrendingSource,
    "google_trends": GoogleTrendsSource,
    "linkedin_hashtags": LinkedInHashtagsSource,
}

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))


def _load_sources_config() -> list[dict]:
    """Load signal_sources.json from app_dir().

    Falls back to an empty list so the worker doesn't crash when no config exists yet.
    """
    try:
        if _ROOT not in sys.path:
            sys.path.insert(0, _ROOT)
        from paths import app_dir  # type: ignore[import]
        config_path = os.path.join(app_dir(), "signal_sources.json")
    except ImportError:
        config_path = os.path.join(_ROOT, "signal_sources.json")

    if not os.path.exists(config_path):
        logger.warning("signal_sources.json not found at %s — no sources configured.", config_path)
        return []

    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)

    # Handle both {"sources": [...]} and plain [...] formats
    if isinstance(data, list):
        return data
    return data.get("sources", [])


def _validate_source(source_def: dict, index: int) -> str | None:
    """Return an error message if the source entry is invalid, else None."""
    source_type = source_def.get("type", "")
    if not source_type:
        return f"entry #{index}: missing 'type' field"
    if source_type not in _SOURCE_REGISTRY:
        return f"entry #{index}: unknown type '{source_type}'"
    if not source_def.get("category"):
        return f"entry #{index} (type={source_type}): missing 'category' field"
    # Type-specific validation
    if source_type == "rss" and not source_def.get("feeds"):
        return f"entry #{index} (type=rss): missing 'feeds' field"
    if source_type == "reddit" and not source_def.get("subreddit"):
        return f"entry #{index} (type=reddit): missing 'subreddit' field"
    return None


def collect(db_path: str | None = None) -> list[Signal]:
    """Run all configured sources, deduplicate, and persist new signals.

    Args:
        db_path: Optional DB path override.

    Returns:
        List of newly inserted Signal objects (with id set).
    """
    sources_config = _load_sources_config()
    if not sources_config:
        logger.info("Collector: no sources configured.")
        return []

    # Load known URLs once to avoid per-signal round-trips
    known_urls: set[str] = signal_repo.get_existing_urls(db_path)
    logger.debug("Collector: %d URLs already in DB.", len(known_urls))

    all_signals: list[Signal] = []

    for idx, source_def in enumerate(sources_config):
        error = _validate_source(source_def, idx)
        if error:
            logger.warning("Collector: invalid source — %s. Skipping.", error)
            continue

        source_type: str = source_def["type"]
        adapter_cls = _SOURCE_REGISTRY[source_type]

        try:
            adapter = adapter_cls()
            fetched = adapter.fetch(source_def)
            all_signals.extend(fetched)
        except Exception as exc:
            logger.error("Source '%s' raised an error: %s", source_type, exc)

    # Deduplicate and persist
    new_signals: list[Signal] = []
    for sig in all_signals:
        if sig.source_url in known_urls:
            continue
        known_urls.add(sig.source_url)  # prevent duplicates within same run
        try:
            sig.id = signal_repo.insert(sig, db_path)
            new_signals.append(sig)
        except Exception as exc:
            logger.error("Failed to insert signal '%s': %s", sig.title[:60], exc)

    logger.info(
        "Collector: %d fetched, %d new, %d duplicates skipped.",
        len(all_signals),
        len(new_signals),
        len(all_signals) - len(new_signals),
    )
    return new_signals
