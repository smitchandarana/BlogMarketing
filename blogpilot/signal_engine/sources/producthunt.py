"""Product Hunt source adapter — fetches today's top products.

Scrapes the Product Hunt homepage since their API requires OAuth.
Config example in signal_sources.json:
  {"type": "producthunt", "category": "startup", "limit": 15}
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import requests

from blogpilot.signal_engine.models.signal import Signal

logger = logging.getLogger(__name__)

_PH_URL = "https://www.producthunt.com"


class ProductHuntSource:
    """Fetches signals from Product Hunt's daily launches."""

    def fetch(self, config: dict) -> list[Signal]:
        """Collect today's Product Hunt launches via page scrape.

        Args:
            config: Must contain 'category'. Optional: 'limit' (default 15).

        Returns:
            List of Signal objects.
        """
        limit = min(config.get("limit", 15), 30)
        category = config.get("category", "startup")

        try:
            resp = requests.get(
                _PH_URL,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PhoenixBot/1.0)"},
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("ProductHunt: fetch failed: %s", exc)
            return []

        signals: list[Signal] = []
        now = datetime.now(timezone.utc).isoformat()

        # Extract product entries from meta tags / JSON-LD or basic patterns
        # PH pages contain structured data we can parse
        titles = re.findall(
            r'data-test="post-name"[^>]*>([^<]+)<', resp.text
        )
        taglines = re.findall(
            r'data-test="post-tagline"[^>]*>([^<]+)<', resp.text
        )
        links = re.findall(
            r'href="(/posts/[^"]+)"', resp.text
        )

        # Deduplicate links
        seen_links: set[str] = set()
        unique_links: list[str] = []
        for link in links:
            if link not in seen_links:
                seen_links.add(link)
                unique_links.append(link)

        count = min(limit, len(titles), len(unique_links))
        for i in range(count):
            title = titles[i].strip() if i < len(titles) else "Untitled"
            tagline = taglines[i].strip() if i < len(taglines) else ""
            url = f"{_PH_URL}{unique_links[i]}" if i < len(unique_links) else _PH_URL

            sig = Signal(
                source="producthunt",
                source_url=url,
                title=title,
                summary=tagline,
                category=category,
                created_at=now,
            )
            sig.set_raw({"tagline": tagline})
            signals.append(sig)

        logger.info("ProductHunt adapter: collected %d signals.", len(signals))
        return signals
