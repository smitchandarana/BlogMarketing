"""Reddit signal source adapter.

Wraps the Reddit fetch logic already present in topic_researcher.py.
Does NOT duplicate that logic — calls it directly via import.
"""

from __future__ import annotations

import logging
import sys
import os

from blogpilot.signal_engine.models.signal import Signal

logger = logging.getLogger(__name__)

# Ensure project root is on path so we can import existing modules
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class RedditSource:
    """Fetches signals from subreddit hot/new listings via existing Reddit scraper."""

    def fetch(self, config: dict) -> list[Signal]:
        """Collect posts from configured subreddits.

        Args:
            config: Must contain 'subreddits': list[str].
                    Optional 'limit': int (posts per subreddit, default 10).
                    Optional 'category': str label (default 'reddit').

        Returns:
            List of Signal objects (unscored, status='new').
        """
        subreddits: list[str] = config.get("subreddits", [])
        limit: int = config.get("limit", 10)
        category: str = config.get("category", "reddit")
        signals: list[Signal] = []

        for sub in subreddits:
            try:
                posts = self._fetch_subreddit(sub, limit)
                for post in posts:
                    source_url = post.get("url", "")
                    if not source_url:
                        continue

                    sig = Signal(
                        source="reddit",
                        source_url=source_url,
                        title=post.get("title", "").strip(),
                        summary=post.get("selftext", "")[:800].strip()
                        or post.get("title", ""),
                        category=category,
                    )
                    sig.set_raw({
                        "subreddit": sub,
                        "score": post.get("score", 0),
                        "num_comments": post.get("num_comments", 0),
                    })
                    signals.append(sig)

            except Exception as exc:
                logger.warning("Reddit fetch failed for r/%s: %s", sub, exc)

        logger.info("Reddit adapter: collected %d signals.", len(signals))
        return signals

    def _fetch_subreddit(self, subreddit: str, limit: int) -> list[dict]:
        """Fetch posts from a subreddit using requests (no auth required for JSON API)."""
        import requests  # already in requirements

        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
        headers = {"User-Agent": "PhoenixMarketingBot/1.0"}

        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        posts = data.get("data", {}).get("children", [])
        return [p["data"] for p in posts if p.get("data")]
