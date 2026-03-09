"""Signal Engine — FastAPI router.

Endpoints:
    GET  /api/signals           → list signals (filter by status, limit)
    GET  /api/signals/{id}      → single signal
    POST /api/signals/collect   → trigger collect + optional score run
    GET  /api/signals/worker    → worker status
"""

from __future__ import annotations

import asyncio
import logging
from fastapi import APIRouter, HTTPException, Query

from blogpilot.signal_engine.schemas import (
    CollectRequest,
    CollectResponse,
    SignalListResponse,
    SignalResponse,
    WorkerStatusResponse,
)
import blogpilot.db.repositories.signals as signal_repo
from blogpilot.signal_engine.workers import signal_worker

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_response(sig) -> SignalResponse:
    return SignalResponse(
        id=sig.id,
        source=sig.source,
        source_url=sig.source_url,
        title=sig.title,
        summary=sig.summary,
        category=sig.category,
        relevance_score=sig.relevance_score,
        status=sig.status,
        created_at=sig.created_at,
    )


@router.get("", response_model=SignalListResponse)
async def list_signals(
    status: str | None = Query(default=None, description="Filter by status: new, processed, dismissed"),
    limit: int = Query(default=50, ge=1, le=500),
) -> SignalListResponse:
    """Return signals ordered by created_at DESC."""
    signals = signal_repo.get_all(status=status, limit=limit)
    return SignalListResponse(
        signals=[_to_response(s) for s in signals],
        total=len(signals),
    )


@router.get("/worker", response_model=WorkerStatusResponse)
async def worker_status() -> WorkerStatusResponse:
    """Return whether the background signal worker is running."""
    return WorkerStatusResponse(running=signal_worker.is_running())


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(signal_id: int) -> SignalResponse:
    """Return a single signal by id."""
    sig = signal_repo.get_by_id(signal_id)
    if sig is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found.")
    return _to_response(sig)


@router.post("/collect", response_model=CollectResponse)
async def collect_signals(body: CollectRequest = CollectRequest()) -> CollectResponse:
    """Trigger an immediate signal collection run.

    Runs synchronously in the request — for large feed sets use the background worker.
    """
    from blogpilot.signal_engine.services.collector import collect
    from blogpilot.signal_engine.services.scorer import score

    try:
        new_signals = await asyncio.to_thread(collect)
        scored_signals = await asyncio.to_thread(score, new_signals) if body.run_scorer else []
        return CollectResponse(
            collected=len(new_signals),
            scored=len(scored_signals),
            timestamp=__import__("datetime").datetime.utcnow().isoformat() + "Z",
        )
    except Exception as exc:
        logger.error("Collect endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
