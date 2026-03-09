"""Content Engine — FastAPI router.

Endpoints:
    GET  /api/content               → list content (filter by status, type, limit)
    GET  /api/content/{id}          → single content item
    POST /api/content/generate      → trigger content generation cycle
    GET  /api/content/worker        → worker status
"""

from __future__ import annotations

import asyncio
import logging
from fastapi import APIRouter, HTTPException, Query

from blogpilot.content_engine.schemas import (
    ContentListResponse,
    ContentResponse,
    GenerateRequest,
    GenerateResponse,
    WorkerStatusResponse,
)
import blogpilot.db.repositories.content as content_repo
from blogpilot.content_engine.workers import content_worker

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_response(c) -> ContentResponse:
    return ContentResponse(
        id=c.id,
        content_type=c.content_type,
        topic=c.topic,
        title=c.title,
        body=c.body,
        insight_id=c.insight_id,
        file_path=c.file_path,
        hashtags=c.hashtags,
        status=c.status,
        created_at=c.created_at,
    )


@router.get("", response_model=ContentListResponse)
async def list_content(
    status: str | None = Query(default=None),
    content_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> ContentListResponse:
    items = content_repo.get_all(status=status, content_type=content_type, limit=limit)
    return ContentListResponse(content=[_to_response(c) for c in items], total=len(items))


@router.get("/worker", response_model=WorkerStatusResponse)
async def worker_status() -> WorkerStatusResponse:
    return WorkerStatusResponse(running=content_worker.is_running())


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(content_id: int) -> ContentResponse:
    c = content_repo.get_by_id(content_id)
    if c is None:
        raise HTTPException(status_code=404, detail=f"Content {content_id} not found.")
    return _to_response(c)


@router.post("/generate", response_model=GenerateResponse)
async def generate_content(body: GenerateRequest = GenerateRequest()) -> GenerateResponse:
    """Trigger content generation.

    - No body: runs full auto-cycle from eligible insights.
    - insight_id: generate only for that insight.
    - topic + content_type: generate standalone content.
    """
    try:
        if body.topic:
            # Standalone generation for a specific topic
            from blogpilot.content_engine.services.blog_service import generate as gen_blog
            from blogpilot.content_engine.services.linkedin_service import generate as gen_li

            if body.content_type == "blog_post":
                c = gen_blog(topic=body.topic)
            else:
                c = gen_li(topic=body.topic)

            if c:
                c.id = content_repo.insert(c)
                return GenerateResponse(insights_processed=0, content_created=1,
                                        timestamp=__import__("datetime").datetime.utcnow().isoformat() + "Z")
            return GenerateResponse(insights_processed=0, content_created=0,
                                    timestamp=__import__("datetime").datetime.utcnow().isoformat() + "Z")
        else:
            result = await asyncio.to_thread(content_worker.run_now)
            return GenerateResponse(**result)
    except Exception as exc:
        logger.error("Generate endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
