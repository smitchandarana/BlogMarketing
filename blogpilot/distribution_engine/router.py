"""Distribution Engine — FastAPI router.

Endpoints:
    POST /api/distribution/distribute   → queue content for publishing
    GET  /api/distribution/queue        → list queue items
    POST /api/distribution/schedule     → reschedule a queue item
    POST /api/distribution/run          → trigger immediate worker run
    GET  /api/distribution/worker       → worker status
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from blogpilot.distribution_engine.schemas import (
    DistributeRequest,
    DistributeResponse,
    QueueItemResponse,
    QueueListResponse,
    ScheduleRequest,
    ScheduleResponse,
    WorkerRunResponse,
    WorkerStatusResponse,
)
import blogpilot.db.repositories.distribution as dist_repo
from blogpilot.distribution_engine.services.distribution_planner import plan
from blogpilot.distribution_engine.workers import distribution_worker

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_response(item) -> QueueItemResponse:
    return QueueItemResponse(
        id=item.id,
        content_id=item.content_id,
        channel=item.channel,
        status=item.status,
        scheduled_time=item.scheduled_time,
        published_at=item.published_at,
        external_url=item.external_url,
        error_message=item.error_message,
        created_at=item.created_at,
    )


@router.post("/distribute", response_model=DistributeResponse)
async def distribute_content(body: DistributeRequest) -> DistributeResponse:
    """Queue a content item for distribution.

    The planner determines channels and scheduled times based on content_type.
    """
    try:
        jobs = plan(content_type=body.content_type, content_id=body.content_id)
        queue_ids: list[int] = []
        for job in jobs:
            from blogpilot.distribution_engine.models.distribution_queue_model import DistributionQueue
            item = DistributionQueue(
                content_id=job["content_id"],
                channel=job["channel"],
                scheduled_time=job["scheduled_time"],
                status="scheduled" if job["scheduled_time"] else "queued",
            )
            qid = dist_repo.insert(item)
            queue_ids.append(qid)

        return DistributeResponse(
            jobs_created=len(queue_ids),
            queue_ids=queue_ids,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
    except Exception as exc:
        logger.error("distribute endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/queue", response_model=QueueListResponse)
async def list_queue(
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> QueueListResponse:
    items = dist_repo.get_all(status=status, channel=channel, limit=limit)
    return QueueListResponse(items=[_to_response(i) for i in items], total=len(items))


@router.post("/schedule", response_model=ScheduleResponse)
async def schedule_item(body: ScheduleRequest) -> ScheduleResponse:
    """Reschedule an existing queue item."""
    item = dist_repo.get_by_id(body.queue_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Queue item {body.queue_id} not found.")
    try:
        dist_repo.update_scheduled_time(body.queue_id, body.scheduled_time)
        return ScheduleResponse(queue_id=body.queue_id, scheduled_time=body.scheduled_time)
    except Exception as exc:
        logger.error("schedule endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/run", response_model=WorkerRunResponse)
async def run_worker() -> WorkerRunResponse:
    """Trigger an immediate distribution cycle."""
    try:
        result = distribution_worker.run_now()
        return WorkerRunResponse(**result)
    except Exception as exc:
        logger.error("distribution run endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/worker", response_model=WorkerStatusResponse)
async def worker_status() -> WorkerStatusResponse:
    return WorkerStatusResponse(running=distribution_worker.is_running())
