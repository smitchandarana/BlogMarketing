"""Engagement Engine — FastAPI router.

All endpoints live under /api/engagement (registered in api/main.py).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from blogpilot.engagement_engine.schemas import (
    EngagementLogEntry,
    EngagementRunResponse,
    EngagementStats,
    InfluencerCreate,
    InfluencerResponse,
    WorkerStatusResponse,
)
from blogpilot.engagement_engine.workers import engagement_worker

router = APIRouter()


# ── Worker control ─────────────────────────────────────────────────────────────

@router.get("/worker", response_model=WorkerStatusResponse)
async def get_worker_status() -> WorkerStatusResponse:
    """Return engagement worker running state and current interval."""
    return WorkerStatusResponse(
        running=engagement_worker.is_running(),
        interval_hours=engagement_worker.get_interval(),
    )


@router.post("/run", response_model=EngagementRunResponse)
async def run_engagement() -> EngagementRunResponse:
    """Trigger one full engagement cycle immediately."""
    result = await asyncio.to_thread(engagement_worker.run_now)
    # Normalise error/skipped returns — fill required int fields with 0
    return EngagementRunResponse(
        posts_scanned=result.get("posts_scanned", 0),
        posts_engaged=result.get("posts_engaged", 0),
        comments_posted=result.get("comments_posted", 0),
        likes_given=result.get("likes_given", 0),
        timestamp=result.get("timestamp", ""),
        skipped=result.get("skipped", False),
        error=result.get("error"),
    )


# ── Feed ───────────────────────────────────────────────────────────────────────

@router.get("/feed")
@router.post("/feed")
async def scan_feed() -> dict:
    """Scan the LinkedIn feed and return extracted posts (no engagement action)."""
    try:
        from blogpilot.engagement_engine.services.feed_scanner import scan, PlaywrightLoginRequired
        posts = await asyncio.to_thread(scan, 2)
        return {
            "posts": [
                {
                    "post_urn": p.post_urn,
                    "author_name": p.author_name,
                    "text": p.text[:300],
                    "likes": p.likes,
                    "comments": p.comments,
                }
                for p in posts
            ],
            "count": len(posts),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Engagement log ─────────────────────────────────────────────────────────────

@router.get("/log")
async def get_log(limit: int = 20, status: str | None = None) -> dict:
    """Return recent engagement log entries."""
    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        sql = "SELECT * FROM engagement_log"
        params: list = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY rowid DESC LIMIT ?"
        params.append(limit)
        with get_connection() as conn:
            conn.row_factory = None
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return {"rows": rows, "count": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stats", response_model=EngagementStats)
async def get_stats() -> EngagementStats:
    """Return cumulative and today's engagement stats."""
    from datetime import date
    today = date.today().isoformat()
    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        with get_connection() as conn:
            total_likes = conn.execute(
                "SELECT COUNT(*) FROM engagement_log WHERE action IN ('like','comment') AND status='done'"
            ).fetchone()[0]
            total_comments = conn.execute(
                "SELECT COUNT(*) FROM engagement_log WHERE action='comment' AND status='done'"
            ).fetchone()[0]
            today_likes = conn.execute(
                "SELECT COUNT(*) FROM engagement_log WHERE action IN ('like','comment') "
                "AND engaged_at LIKE ? AND status='done'", (f"{today}%",)
            ).fetchone()[0]
            today_comments = conn.execute(
                "SELECT COUNT(*) FROM engagement_log WHERE action='comment' "
                "AND engaged_at LIKE ? AND status='done'", (f"{today}%",)
            ).fetchone()[0]
            total_posts = conn.execute(
                "SELECT COUNT(*) FROM engagement_log WHERE action != 'skip'"
            ).fetchone()[0]
        rate = round(total_likes / max(total_posts, 1), 3)
        return EngagementStats(
            total_likes=total_likes,
            total_comments=total_comments,
            today_likes=today_likes,
            today_comments=today_comments,
            engagement_rate=rate,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/viral")
async def get_viral_posts(days: int = 7) -> dict:
    """Return posts detected as viral in the last N days."""
    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        with get_connection() as conn:
            conn.row_factory = None
            cur = conn.execute(
                "SELECT post_urn, author_name, post_text, viral_score, engaged_at "
                "FROM engagement_log "
                "WHERE viral_score >= 0.5 AND engaged_at >= datetime('now', ?) "
                "ORDER BY viral_score DESC LIMIT 50",
                (f"-{days} days",),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return {"rows": rows, "count": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Influencers ────────────────────────────────────────────────────────────────

@router.get("/influencers")
async def list_influencers() -> dict:
    """List all active influencer targets."""
    from blogpilot.engagement_engine.services.influencer_monitor import get_influencers
    influencers = get_influencers()
    return {
        "influencers": [
            {
                "id": inf.id, "name": inf.name, "linkedin_url": inf.linkedin_url,
                "category": inf.category, "priority": inf.priority,
                "last_checked": inf.last_checked,
            }
            for inf in influencers
        ]
    }


@router.post("/influencers", status_code=201)
async def add_influencer(body: InfluencerCreate) -> dict:
    """Add a new influencer target."""
    from blogpilot.engagement_engine.services.influencer_monitor import add_influencer
    new_id = add_influencer(
        name=body.name,
        linkedin_url=body.linkedin_url,
        category=body.category,
        priority=body.priority,
    )
    return {"id": new_id, "name": body.name, "linkedin_url": body.linkedin_url}


@router.delete("/influencers/{influencer_id}")
async def remove_influencer(influencer_id: int) -> dict:
    """Soft-delete an influencer target."""
    from blogpilot.engagement_engine.services.influencer_monitor import remove_influencer
    remove_influencer(influencer_id)
    return {"id": influencer_id, "action": "removed"}
