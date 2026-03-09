"""Insight Engine — FastAPI router.

Endpoints:
    GET  /api/insights           → list insights (filter by status, limit)
    GET  /api/insights/{id}      → single insight
    POST /api/insights/generate  → trigger insight generation cycle
    GET  /api/insights/worker    → worker status
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query

from blogpilot.insight_engine.schemas import (
    GenerateRequest,
    GenerateResponse,
    InsightListResponse,
    InsightResponse,
    WorkerStatusResponse,
)
import blogpilot.db.repositories.insights as insight_repo
from blogpilot.insight_engine.workers import insight_worker

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_response(ins) -> InsightResponse:
    return InsightResponse(
        id=ins.id,
        title=ins.title,
        summary=ins.summary,
        category=ins.category,
        signal_ids=ins.signal_ids,
        confidence=ins.confidence,
        action_items=ins.action_items,
        status=ins.status,
        created_at=ins.created_at,
    )


@router.get("", response_model=InsightListResponse)
async def list_insights(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> InsightListResponse:
    insights = insight_repo.get_all(status=status, limit=limit)
    return InsightListResponse(insights=[_to_response(i) for i in insights], total=len(insights))


@router.get("/worker", response_model=WorkerStatusResponse)
async def worker_status() -> WorkerStatusResponse:
    return WorkerStatusResponse(running=insight_worker.is_running())


@router.get("/{insight_id}", response_model=InsightResponse)
async def get_insight(insight_id: int) -> InsightResponse:
    ins = insight_repo.get_by_id(insight_id)
    if ins is None:
        raise HTTPException(status_code=404, detail=f"Insight {insight_id} not found.")
    return _to_response(ins)


@router.post("/generate", response_model=GenerateResponse)
async def generate_insights(body: GenerateRequest = GenerateRequest()) -> GenerateResponse:
    try:
        result = insight_worker.run_now()
        return GenerateResponse(**result)
    except Exception as exc:
        logger.error("Generate endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
