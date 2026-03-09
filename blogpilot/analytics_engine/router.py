"""Analytics Engine — FastAPI router.

Endpoints:
    GET  /api/analytics/dashboard         → aggregated performance data
    GET  /api/analytics/content/{id}      → metrics for a single content item
    GET  /api/analytics/top-content       → top N content by performance_score
    POST /api/analytics/collect           → trigger immediate collection + analysis
    GET  /api/analytics/worker            → worker status
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from blogpilot.analytics_engine.schemas import (
    CollectResponse,
    ContentMetricsResponse,
    DashboardResponse,
    MetricsResponse,
    TopContentItem,
    TopContentResponse,
    WorkerStatusResponse,
)
import blogpilot.db.repositories.metrics as metrics_repo
from blogpilot.analytics_engine.services.performance_analyzer import (
    get_dashboard,
    get_top_content,
)
from blogpilot.analytics_engine.workers import analytics_worker

logger = logging.getLogger(__name__)
router = APIRouter()


def _metrics_to_response(m) -> MetricsResponse:
    return MetricsResponse(
        id=m.id,
        content_id=m.content_id,
        channel=m.channel,
        impressions=m.impressions,
        clicks=m.clicks,
        likes=m.likes,
        comments=m.comments,
        engagements=m.engagements,
        shares=m.shares,
        engagement_score=m.engagement_score,
        recorded_at=m.recorded_at,
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard() -> DashboardResponse:
    """Return aggregated performance data for the dashboard."""
    try:
        data = get_dashboard()
        return DashboardResponse(**data)
    except Exception as exc:
        logger.error("dashboard endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/content/{content_id}", response_model=ContentMetricsResponse)
async def content_metrics(content_id: int) -> ContentMetricsResponse:
    """Return all metrics records for a specific content item."""
    records = metrics_repo.get_by_content(content_id)
    if not records:
        raise HTTPException(status_code=404, detail=f"No metrics found for content {content_id}.")
    return ContentMetricsResponse(
        content_id=content_id,
        records=[_metrics_to_response(m) for m in records],
    )


@router.get("/top-content", response_model=TopContentResponse)
async def top_content(
    limit: int = Query(default=10, ge=1, le=50),
) -> TopContentResponse:
    """Return top-performing content items ordered by performance_score."""
    items = get_top_content(limit=limit)
    return TopContentResponse(
        items=[TopContentItem(**item) for item in items],
        total=len(items),
    )


@router.post("/collect", response_model=CollectResponse)
async def collect() -> CollectResponse:
    """Trigger an immediate metrics collection and analysis cycle."""
    try:
        result = analytics_worker.run_now()
        return CollectResponse(
            linkedin_collected=result.get("linkedin_collected", 0),
            website_collected=result.get("website_collected", 0),
            content_scored=result.get("content_scored", 0),
            timestamp=result.get("timestamp", ""),
        )
    except Exception as exc:
        logger.error("collect endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/worker", response_model=WorkerStatusResponse)
async def worker_status() -> WorkerStatusResponse:
    return WorkerStatusResponse(running=analytics_worker.is_running())
