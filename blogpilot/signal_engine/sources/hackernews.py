"""Hacker News source adapter — fetches top/best stories from the HN API.

Uses the official HN Firebase API (no API key required).
Config example in signal_sources.json:
  {"type": "hackernews", "category": "tech", "limit": 20, "feed": "topstories"}
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from blogpilot.signal_engine.models.signal import Signal

logger = logging.getLogger(__name__)

_HN_BASE = "https://hacker-news.firebaseio.com/v0"
_VALID_FEEDS = ("topstories", "beststories", "newstories", "showstories", "askstories")


class HackerNewsSource:
    """Fetches signals from Hacker News top/best/new stories."""

    def fetch(self, config: dict) -> list[Signal]:
        """Collect stories from Hacker News.

        Args:
            config: Must contain 'category'. Optional: 'feed' (default topstories),
                    'limit' (default 20).

        Returns:
            List of Signal objects.
        """
        feed = config.get("feed", "topstories")
        if feed not in _VALID_FEEDS:
            feed = "topstories"
        limit = min(config.get("limit", 20), 50)
        category = config.get("category", "tech")

        try:
            resp = requests.get(f"{_HN_BASE}/{feed}.json", timeout=15)
            resp.raise_for_status()
            story_ids = resp.json()[:limit]
        except Exception as exc:
            logger.error("HN: failed to fetch %s: %s", feed, exc)
            return []

        signals: list[Signal] = []
        for story_id in story_ids:
            try:
                item_resp = requests.get(f"{_HN_BASE}/item/{story_id}.json", timeout=10)
                item_resp.raise_for_status()
                item = item_resp.json()
                if not item or item.get("type") != "story":
                    continue

                title = item.get("title", "")
                url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                score = item.get("score", 0)
                descendants = item.get("descendants", 0)
                by = item.get("by", "")
                ts = datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc).isoformat()

                summary = f"Score: {score} | Comments: {descendants} | By: {by}"
                if item.get("text"):
                    summary += f" | {item['text'][:300]}"

                sig = Signal(
                    source="hackernews",
                    source_url=url,
                    title=title,
                    summary=summary,
                    category=category,
                    created_at=ts,
                )
                sig.set_raw({"hn_id": story_id, "score": score, "comments": descendants})
                signals.append(sig)

            except Exception as exc:
                logger.debug("HN: failed to fetch item %s: %s", story_id, exc)

        logger.info("HackerNews adapter: collected %d signals from %s.", len(signals), feed)
        return signals
