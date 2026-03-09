"""Metrics Collector — fetches analytics from LinkedIn API and Google Analytics.

Collection is best-effort:
  - LinkedIn: requires LINKEDIN_ACCESS_TOKEN (uses existing env var)
  - Google Analytics: requires GA_PROPERTY_ID (skipped silently if absent)

Both sources normalize to the Metrics dataclass before storage.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

import blogpilot.db.repositories.content as content_repo
import blogpilot.db.repositories.distribution as dist_repo
import blogpilot.db.repositories.metrics as metrics_repo
from blogpilot.analytics_engine.models.metrics_model import Metrics

logger = logging.getLogger(__name__)

_LI_API = "https://api.linkedin.com/v2"


def collect_all(db_path: str | None = None) -> dict:
    """Run all collectors and return a summary.

    Returns:
        dict with keys: linkedin_collected, website_collected, errors.
    """
    li_count = _collect_linkedin(db_path)
    ga_count = _collect_website(db_path)
    summary = {"linkedin_collected": li_count, "website_collected": ga_count}
    logger.info("Metrics collection complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------

def _collect_linkedin(db_path: str | None = None) -> int:
    """Collect LinkedIn post analytics for all published LinkedIn content."""
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    if not token:
        logger.warning("LINKEDIN_ACCESS_TOKEN not set — LinkedIn metrics skipped.")
        return 0

    try:
        import requests
    except ImportError:
        logger.warning("requests not installed — LinkedIn metrics skipped.")
        return 0

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Get all published LinkedIn distribution jobs to find share URNs
    published_jobs = dist_repo.get_all(status="published", channel="linkedin", limit=100, db_path=db_path)
    collected = 0

    for job in published_jobs:
        if not job.external_url:
            continue
        try:
            share_urn = _extract_share_urn(job.external_url)
            if not share_urn:
                continue

            resp = requests.get(
                f"{_LI_API}/organizationalEntityShareStatistics",
                headers=headers,
                params={"q": "organizationalEntity", "shares[0]": share_urn},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.debug("LinkedIn stats %s → HTTP %d", share_urn, resp.status_code)
                continue

            data = resp.json()
            elements = data.get("elements", [])
            if not elements:
                continue

            stats = elements[0].get("totalShareStatistics", {})
            impressions = stats.get("impressionCount", 0)
            clicks = stats.get("clickCount", 0)
            likes = stats.get("likeCount", 0)
            comments = stats.get("commentCount", 0)
            shares = stats.get("shareCount", 0)
            engagement = Metrics.compute_engagement_score(likes, comments, shares, impressions)

            m = Metrics(
                content_id=job.content_id,
                channel="linkedin",
                impressions=impressions,
                clicks=clicks,
                likes=likes,
                comments=comments,
                engagements=likes + comments + shares,
                shares=shares,
                engagement_score=engagement,
                raw_payload=json.dumps(stats),
            )
            metrics_repo.upsert(m, db_path)
            collected += 1

        except Exception as exc:
            logger.warning("LinkedIn metrics failed for job %d: %s", job.id, exc)

    return collected


def _extract_share_urn(url: str) -> str | None:
    """Extract share URN from a LinkedIn post URL."""
    # URL format: https://www.linkedin.com/feed/update/urn:li:share:XXXXXXX
    if "feed/update/" in url:
        return url.split("feed/update/")[-1].split("?")[0]
    return None


# ---------------------------------------------------------------------------
# Website / Google Analytics
# ---------------------------------------------------------------------------

def _collect_website(db_path: str | None = None) -> int:
    """Collect website metrics via Google Analytics Data API (opt-in)."""
    property_id = os.getenv("GA_PROPERTY_ID", "")
    if not property_id:
        logger.debug("GA_PROPERTY_ID not set — website metrics skipped.")
        return 0

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient  # type: ignore[import]
        from google.analytics.data_v1beta.types import (  # type: ignore[import]
            DateRange, Dimension, Metric, RunReportRequest,
        )
    except ImportError:
        logger.debug("google-analytics-data not installed — website metrics skipped.")
        return 0

    published_jobs = dist_repo.get_all(status="published", channel="website", limit=100, db_path=db_path)
    collected = 0

    try:
        client = BetaAnalyticsDataClient()
        for job in published_jobs:
            if not job.external_url:
                continue
            try:
                path = "/" + job.external_url.split("phoenixsolution.in", 1)[-1].lstrip("/")
                request = RunReportRequest(
                    property=f"properties/{property_id}",
                    dimensions=[Dimension(name="pagePath")],
                    metrics=[
                        Metric(name="screenPageViews"),
                        Metric(name="sessions"),
                    ],
                    date_ranges=[DateRange(start_date="2020-01-01", end_date="today")],
                    dimension_filter={
                        "filter": {
                            "field_name": "pagePath",
                            "string_filter": {"match_type": "EXACT", "value": path},
                        }
                    },
                )
                response = client.run_report(request)
                if not response.rows:
                    continue

                row = response.rows[0]
                page_views = int(row.metric_values[0].value)
                sessions = int(row.metric_values[1].value)

                m = Metrics(
                    content_id=job.content_id,
                    channel="website",
                    impressions=page_views,
                    clicks=sessions,
                    engagement_score=round(sessions / max(page_views, 1), 6),
                )
                metrics_repo.upsert(m, db_path)
                collected += 1

            except Exception as exc:
                logger.warning("GA metrics failed for job %d: %s", job.id, exc)

    except Exception as exc:
        logger.error("GA client error: %s", exc)

    return collected
