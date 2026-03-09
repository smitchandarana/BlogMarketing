"""RSS/Atom feed source adapter.

Reads feed URLs from config['feeds'] and returns one Signal per entry.
Requires: feedparser (added to requirements.txt)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from blogpilot.signal_engine.models.signal import Signal

logger = logging.getLogger(__name__)


class RssSource:
    """Fetches signals from a list of RSS/Atom feed URLs."""

    def fetch(self, config: dict) -> list[Signal]:
        """Collect entries from all configured RSS feeds.

        Args:
            config: Must contain 'feeds': list[str] of feed URLs.
                    Optional 'category': str label for all entries.

        Returns:
            List of Signal objects (unscored, status='new').
        """
        try:
            import feedparser  # type: ignore[import]
        except ImportError:
            logger.error("feedparser not installed — run: pip install feedparser")
            return []

        feeds: list[str] = config.get("feeds", [])
        category: str = config.get("category", "industry")
        signals: list[Signal] = []

        for url in feeds:
            try:
                parsed = feedparser.parse(url)
                feed_title = parsed.feed.get("title", url)
                logger.debug("RSS: %s — %d entries", feed_title, len(parsed.entries))

                for entry in parsed.entries:
                    source_url = entry.get("link", "")
                    if not source_url:
                        continue

                    title = entry.get("title", "").strip()
                    summary = (
                        entry.get("summary", "")
                        or entry.get("description", "")
                        or ""
                    ).strip()[:1000]  # cap raw summary

                    # Parse published date if available
                    published = entry.get("published_parsed")
                    if published:
                        try:
                            ts = datetime(*published[:6], tzinfo=timezone.utc).isoformat()
                        except Exception:
                            ts = datetime.now(timezone.utc).isoformat()
                    else:
                        ts = datetime.now(timezone.utc).isoformat()

                    sig = Signal(
                        source="rss",
                        source_url=source_url,
                        title=title,
                        summary=summary,
                        category=category,
                        created_at=ts,
                    )
                    sig.set_raw({"feed": feed_title, "link": source_url})
                    signals.append(sig)

            except Exception as exc:
                logger.warning("RSS fetch failed for %s: %s", url, exc)

        logger.info("RSS adapter: collected %d signals.", len(signals))
        return signals
