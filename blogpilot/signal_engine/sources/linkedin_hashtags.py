"""LinkedIn Hashtag source adapter — converts LinkedIn hashtag trends into signals.

Unlike the engagement engine's hashtag_scanner (which uses Playwright for real
browser scraping), this adapter creates signals from the configured hashtag list
to feed into the signal → insight → content pipeline.

Config example in signal_sources.json:
  {"type": "linkedin_hashtags", "category": "social", "hashtags_file": "Prompts/Hashtags.txt"}
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from blogpilot.signal_engine.models.signal import Signal

logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))


class LinkedInHashtagsSource:
    """Creates signals from configured LinkedIn hashtags for trend monitoring."""

    def fetch(self, config: dict) -> list[Signal]:
        """Generate signal entries from the hashtag list.

        Args:
            config: Must contain 'category'. Optional: 'hashtags_file' path.

        Returns:
            List of Signal objects representing hashtag trend monitors.
        """
        category = config.get("category", "social")
        hashtags_file = config.get("hashtags_file", "Prompts/Hashtags.txt")

        # Resolve path
        path = Path(hashtags_file)
        if not path.is_absolute():
            path = Path(_ROOT) / hashtags_file

        if not path.exists():
            logger.warning("LinkedIn Hashtags: file not found: %s", path)
            return []

        hashtags: list[str] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                tag = line.strip().lstrip("#")
                if tag:
                    hashtags.append(tag)

        if not hashtags:
            return []

        signals: list[Signal] = []
        now = datetime.now(timezone.utc).isoformat()

        for tag in hashtags:
            url = f"https://www.linkedin.com/feed/hashtag/{tag.lower()}/"
            sig = Signal(
                source="linkedin_hashtags",
                source_url=url,
                title=f"LinkedIn Hashtag: #{tag}",
                summary=f"Monitor trending content under #{tag} on LinkedIn.",
                category=category,
                created_at=now,
            )
            sig.set_raw({"hashtag": tag, "platform": "linkedin"})
            signals.append(sig)

        logger.info("LinkedIn Hashtags adapter: created %d signals.", len(signals))
        return signals
