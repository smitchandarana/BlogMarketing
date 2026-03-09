"""Google Trends source adapter — fetches daily trending searches.

Uses the Google Trends RSS feed for daily trending searches (no API key required).
Config example in signal_sources.json:
  {"type": "google_trends", "category": "trending", "geo": "US", "limit": 20}
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from blogpilot.signal_engine.models.signal import Signal

logger = logging.getLogger(__name__)

_TRENDS_RSS_URL = "https://trends.google.com/trends/trendingsearches/daily/rss"


class GoogleTrendsSource:
    """Fetches signals from Google Trends daily trending searches RSS."""

    def fetch(self, config: dict) -> list[Signal]:
        """Collect trending search topics from Google Trends.

        Args:
            config: Must contain 'category'. Optional: 'geo' (default 'US'),
                    'limit' (default 20).

        Returns:
            List of Signal objects.
        """
        geo = config.get("geo", "US")
        limit = min(config.get("limit", 20), 30)
        category = config.get("category", "trending")

        try:
            import feedparser  # type: ignore[import]
        except ImportError:
            logger.error("feedparser not installed — required for Google Trends RSS.")
            return []

        url = f"{_TRENDS_RSS_URL}?geo={geo}"

        try:
            parsed = feedparser.parse(url)
        except Exception as exc:
            logger.error("Google Trends: RSS parse failed: %s", exc)
            return []

        signals: list[Signal] = []

        for entry in parsed.entries[:limit]:
            title = entry.get("title", "").strip()
            if not title:
                continue

            link = entry.get("link", f"https://trends.google.com/trends/explore?q={title}")
            summary = entry.get("summary", "").strip()

            # Extract traffic volume if present
            traffic = entry.get("ht_approx_traffic", "")
            if traffic:
                summary = f"~{traffic} searches | {summary}" if summary else f"~{traffic} searches"

            # Parse published date
            published = entry.get("published_parsed")
            if published:
                try:
                    ts = datetime(*published[:6], tzinfo=timezone.utc).isoformat()
                except Exception:
                    ts = datetime.now(timezone.utc).isoformat()
            else:
                ts = datetime.now(timezone.utc).isoformat()

            sig = Signal(
                source="google_trends",
                source_url=link,
                title=title,
                summary=summary[:500],
                category=category,
                created_at=ts,
            )
            sig.set_raw({"geo": geo, "traffic": traffic})
            signals.append(sig)

        logger.info("Google Trends adapter: collected %d signals (geo=%s).", len(signals), geo)
        return signals
