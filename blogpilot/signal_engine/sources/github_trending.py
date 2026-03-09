"""GitHub Trending source adapter — fetches trending repositories.

Scrapes GitHub's trending page (no API key required).
Config example in signal_sources.json:
  {"type": "github_trending", "category": "tech", "language": "python", "since": "daily"}
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import requests

from blogpilot.signal_engine.models.signal import Signal

logger = logging.getLogger(__name__)

_GH_TRENDING_URL = "https://github.com/trending"


class GitHubTrendingSource:
    """Fetches signals from GitHub trending repositories."""

    def fetch(self, config: dict) -> list[Signal]:
        """Collect trending GitHub repos.

        Args:
            config: Must contain 'category'. Optional: 'language' (e.g. 'python'),
                    'since' ('daily', 'weekly', 'monthly'), 'limit' (default 15).

        Returns:
            List of Signal objects.
        """
        language = config.get("language", "")
        since = config.get("since", "daily")
        limit = min(config.get("limit", 15), 25)
        category = config.get("category", "tech")

        url = _GH_TRENDING_URL
        if language:
            url += f"/{language}"
        url += f"?since={since}"

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PhoenixBot/1.0)"},
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("GitHub Trending: fetch failed: %s", exc)
            return []

        signals: list[Signal] = []
        now = datetime.now(timezone.utc).isoformat()

        # Parse repo entries from the trending page HTML
        # Each repo is in an <article class="Box-row">
        repo_blocks = re.findall(
            r'<article class="Box-row">(.*?)</article>', resp.text, re.DOTALL
        )

        for block in repo_blocks[:limit]:
            try:
                # Repo name: <a href="/owner/repo">
                name_match = re.search(r'href="(/[^"]+)"[^>]*>\s*<span[^>]*>[^<]*</span>\s*/\s*<span[^>]*>([^<]+)</span>', block)
                if not name_match:
                    # Simpler fallback
                    name_match = re.search(r'href="(/[^/]+/[^"]+)"', block)
                    if not name_match:
                        continue

                repo_path = name_match.group(1).strip()
                repo_url = f"https://github.com{repo_path}"
                repo_name = repo_path.lstrip("/")

                # Description
                desc_match = re.search(r'<p class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
                description = desc_match.group(1).strip() if desc_match else ""
                description = re.sub(r"<[^>]+>", "", description).strip()

                # Stars today
                stars_match = re.search(r'(\d[\d,]*)\s*stars\s*today', block)
                stars_today = int(stars_match.group(1).replace(",", "")) if stars_match else 0

                # Total stars
                total_stars_match = re.search(r'class="Link[^"]*"[^>]*>\s*(\d[\d,]*)\s*</a>', block)
                total_stars = int(total_stars_match.group(1).replace(",", "")) if total_stars_match else 0

                # Language
                lang_match = re.search(r'<span[^>]*itemprop="programmingLanguage"[^>]*>([^<]+)</span>', block)
                lang = lang_match.group(1).strip() if lang_match else ""

                summary = description
                if stars_today:
                    summary += f" | +{stars_today} stars today"
                if total_stars:
                    summary += f" | {total_stars:,} total stars"
                if lang:
                    summary += f" | {lang}"

                sig = Signal(
                    source="github_trending",
                    source_url=repo_url,
                    title=repo_name,
                    summary=summary.strip(" |"),
                    category=category,
                    created_at=now,
                )
                sig.set_raw({"stars_today": stars_today, "total_stars": total_stars, "language": lang})
                signals.append(sig)

            except Exception as exc:
                logger.debug("GitHub Trending: parse error: %s", exc)

        logger.info("GitHub Trending adapter: collected %d signals (%s, %s).", len(signals), language or "all", since)
        return signals
