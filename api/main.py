"""Phoenix Marketing Intelligence Engine — FastAPI application entry point.

Start the server:
    uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import sys
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure project root is importable (handles both dev and frozen EXE contexts)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logger = logging.getLogger(__name__)

import time as _time_mod

APP_VERSION = "1.0.0"
_startup_time = _time_mod.time()

# Runtime config file — persists interval overrides across GUI sessions
_RUNTIME_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "runtime_config.json")
_DEFAULT_RUNTIME_CONFIG = {
    "content_confidence_threshold": 0.5,
    "content_max_per_cycle": 20,
    "groq_model": "llama-3.3-70b-versatile",
}


def _load_runtime_config() -> dict:
    if os.path.exists(_RUNTIME_CONFIG_PATH):
        try:
            with open(_RUNTIME_CONFIG_PATH) as f:
                return {**_DEFAULT_RUNTIME_CONFIG, **json.load(f)}
        except Exception:
            pass
    return dict(_DEFAULT_RUNTIME_CONFIG)


def _save_runtime_config(data: dict) -> None:
    with open(_RUNTIME_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Run startup tasks before the server accepts requests."""
    logger.info("Phoenix Marketing Intelligence Engine starting up (v%s).", APP_VERSION)

    # Initialize existing posts table (backward compatible)
    try:
        from database import init_db  # type: ignore[import]
        init_db()
        logger.info("Existing database initialized.")
    except Exception as exc:
        logger.warning("Could not initialize existing database: %s", exc)

    # Apply new engine table migrations
    try:
        from blogpilot.db.migrations import run_migrations
        run_migrations()
        logger.info("Engine migrations applied.")
    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        raise

    # Start signal worker (every 6 hours)
    try:
        from blogpilot.signal_engine.workers.signal_worker import start as start_signal_worker
        start_signal_worker(interval_hours=6)
        logger.info("Signal worker started.")
    except Exception as exc:
        logger.warning("Signal worker could not start: %s", exc)

    # Start insight worker (every 12 hours — runs after signals accumulate)
    try:
        from blogpilot.insight_engine.workers.insight_worker import start as start_insight_worker
        start_insight_worker(interval_hours=12)
        logger.info("Insight worker started.")
    except Exception as exc:
        logger.warning("Insight worker could not start: %s", exc)

    # Start content worker (every 24 hours — runs after insights are ranked)
    try:
        from blogpilot.content_engine.workers.content_worker import start as start_content_worker
        start_content_worker(interval_hours=24)
        logger.info("Content worker started.")
    except Exception as exc:
        logger.warning("Content worker could not start: %s", exc)

    # Start distribution worker (every 30 minutes — publishes due queue items)
    try:
        from blogpilot.distribution_engine.workers.distribution_worker import start as start_dist_worker
        start_dist_worker(interval_minutes=30)
        logger.info("Distribution worker started.")
    except Exception as exc:
        logger.warning("Distribution worker could not start: %s", exc)

    # Start analytics worker (every 24 hours — collect metrics + score content)
    try:
        from blogpilot.analytics_engine.workers.analytics_worker import start as start_analytics_worker
        start_analytics_worker(interval_hours=24)
        logger.info("Analytics worker started.")
    except Exception as exc:
        logger.warning("Analytics worker could not start: %s", exc)

    # Start engagement worker only if opted in (every 2 hours)
    if os.environ.get("ENABLE_ENGAGEMENT", "").lower() == "true":
        try:
            from blogpilot.engagement_engine.workers.engagement_worker import start as start_engagement_worker
            start_engagement_worker(interval_hours=2)
            logger.info("Engagement worker started.")
        except Exception as exc:
            logger.warning("Engagement worker could not start: %s", exc)

    yield  # Server is running

    # Graceful shutdown — all workers
    for stop_fn_path in [
        ("blogpilot.signal_engine.workers.signal_worker", "stop"),
        ("blogpilot.insight_engine.workers.insight_worker", "stop"),
        ("blogpilot.content_engine.workers.content_worker", "stop"),
        ("blogpilot.distribution_engine.workers.distribution_worker", "stop"),
        ("blogpilot.analytics_engine.workers.analytics_worker", "stop"),
        ("blogpilot.engagement_engine.workers.engagement_worker", "stop"),
    ]:
        try:
            import importlib
            mod = importlib.import_module(stop_fn_path[0])
            getattr(mod, stop_fn_path[1])()
        except Exception:
            pass

    logger.info("Phoenix Marketing Intelligence Engine shutting down.")


def _worker_action(engine: str, action: str, interval: int | None = None) -> None:
    """Stop / start a named worker module."""
    module_map = {
        "signal":       "blogpilot.signal_engine.workers.signal_worker",
        "insight":      "blogpilot.insight_engine.workers.insight_worker",
        "content":      "blogpilot.content_engine.workers.content_worker",
        "distribution": "blogpilot.distribution_engine.workers.distribution_worker",
        "analytics":    "blogpilot.analytics_engine.workers.analytics_worker",
        "engagement":   "blogpilot.engagement_engine.workers.engagement_worker",
    }
    if engine not in module_map:
        raise HTTPException(status_code=404, detail=f"Unknown engine: {engine}")
    import importlib
    mod = importlib.import_module(module_map[engine])
    if action == "stop":
        mod.stop()
    elif action == "start":
        if engine == "distribution":
            mod.start(interval_minutes=interval or mod.get_interval())
        else:
            mod.start(interval_hours=interval or mod.get_interval())


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Phoenix Marketing Intelligence Engine",
        description="Local-first AI marketing automation system for Phoenix Solutions.",
        version=APP_VERSION,
        lifespan=lifespan,
    )

    # CORS — allow Next.js dashboard on localhost:3000
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global error handler ──────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc)[:200]},
        )

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health() -> dict:
        return {"status": "ok", "version": APP_VERSION}

    # ── System status — last pipeline run summary ─────────────────────────────
    @app.get("/api/system/status", tags=["System"])
    async def system_status() -> dict:
        try:
            from automation.pipeline import get_status
            return get_status()
        except Exception:
            return {"last_run": None, "signals_collected": 0, "insights_generated": 0,
                    "content_created": 0, "jobs_published": 0, "metrics_collected": 0}

    # ── Workers status + control ──────────────────────────────────────────────
    @app.get("/api/system/workers", tags=["System"])
    async def get_workers() -> dict:
        """Return running state and current interval for all 5 workers."""
        from blogpilot.signal_engine.workers import signal_worker
        from blogpilot.insight_engine.workers import insight_worker
        from blogpilot.content_engine.workers import content_worker
        from blogpilot.distribution_engine.workers import distribution_worker
        from blogpilot.analytics_engine.workers import analytics_worker
        return {
            "signal":       {"running": signal_worker.is_running(),       "interval_hours": signal_worker.get_interval()},
            "insight":      {"running": insight_worker.is_running(),      "interval_hours": insight_worker.get_interval()},
            "content":      {"running": content_worker.is_running(),      "interval_hours": content_worker.get_interval()},
            "distribution": {"running": distribution_worker.is_running(), "interval_minutes": distribution_worker.get_interval()},
            "analytics":    {"running": analytics_worker.is_running(),    "interval_hours": analytics_worker.get_interval()},
        }

    @app.post("/api/system/workers/{engine}/stop", tags=["System"])
    async def stop_worker(engine: str) -> dict:
        """Stop a specific worker."""
        _worker_action(engine, "stop")
        return {"engine": engine, "action": "stopped"}

    @app.post("/api/system/workers/{engine}/start", tags=["System"])
    async def start_worker(engine: str) -> dict:
        """Start a specific worker with its current interval."""
        _worker_action(engine, "start")
        return {"engine": engine, "action": "started"}

    @app.post("/api/system/workers/{engine}/restart", tags=["System"])
    async def restart_worker(engine: str, body: dict) -> dict:
        """Restart a worker with a new interval. Body: {interval_hours} or {interval_minutes}."""
        interval = body.get("interval_hours") or body.get("interval_minutes")
        if interval is None or not isinstance(interval, int) or interval < 1:
            raise HTTPException(status_code=422, detail="interval_hours or interval_minutes (int >= 1) required")
        _worker_action(engine, "stop")
        _worker_action(engine, "start", interval=interval)
        key = "interval_hours" if engine != "distribution" else "interval_minutes"
        return {"engine": engine, "action": "restarted", key: interval}

    # ── Observability / Metrics ───────────────────────────────────────────────
    @app.get("/api/system/metrics", tags=["System"])
    async def system_metrics() -> dict:
        """Return operational metrics for monitoring and debugging."""
        import time
        from blogpilot.db.connection import get_connection

        metrics: dict = {
            "version": APP_VERSION,
            "uptime_seconds": int(time.time() - _startup_time),
        }

        # Database stats
        try:
            with get_connection() as conn:
                conn.row_factory = None
                for table in ("signals", "insights", "content", "engagement_log"):
                    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    metrics[f"db_{table}_count"] = row[0] if row else 0

                # Today's engagement stats
                from datetime import date
                today = date.today().isoformat()
                row = conn.execute(
                    "SELECT COUNT(*) FROM engagement_log WHERE engaged_at LIKE ? AND status='done'",
                    (f"{today}%",),
                ).fetchone()
                metrics["engagement_today"] = row[0] if row else 0

                # Author metrics coverage
                try:
                    row = conn.execute("SELECT COUNT(*) FROM author_metrics").fetchone()
                    metrics["authors_tracked"] = row[0] if row else 0
                except Exception:
                    metrics["authors_tracked"] = 0
        except Exception as exc:
            metrics["db_error"] = str(exc)[:100]

        # Worker states
        try:
            from blogpilot.signal_engine.workers import signal_worker
            from blogpilot.insight_engine.workers import insight_worker
            from blogpilot.content_engine.workers import content_worker
            from blogpilot.distribution_engine.workers import distribution_worker
            from blogpilot.analytics_engine.workers import analytics_worker
            metrics["workers_running"] = sum([
                signal_worker.is_running(),
                insight_worker.is_running(),
                content_worker.is_running(),
                distribution_worker.is_running(),
                analytics_worker.is_running(),
            ])
        except Exception:
            pass

        return metrics

    @app.get("/api/system/health/deep", tags=["System"])
    async def deep_health() -> dict:
        """Deep health check — verifies DB connectivity and worker health."""
        checks: dict = {"status": "ok", "version": APP_VERSION}

        # DB check
        try:
            from blogpilot.db.connection import get_connection
            with get_connection() as conn:
                conn.execute("SELECT 1").fetchone()
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = f"error: {exc}"
            checks["status"] = "degraded"

        # LLM check
        try:
            from llm_client import get_client  # type: ignore[import]
            get_client()
            checks["llm"] = "ok"
        except Exception as exc:
            checks["llm"] = f"error: {exc}"
            checks["status"] = "degraded"

        # Workers
        try:
            from blogpilot.signal_engine.workers import signal_worker
            checks["signal_worker"] = "running" if signal_worker.is_running() else "stopped"
        except Exception:
            checks["signal_worker"] = "unavailable"

        return checks

    # ── Runtime config ────────────────────────────────────────────────────────
    @app.get("/api/system/config", tags=["System"])
    async def get_config() -> dict:
        import json as _json
        cfg = _load_runtime_config()
        try:
            with open(os.path.join(_PROJECT_ROOT, "signal_sources.json")) as f:
                sources = _json.load(f)
            cfg["signal_sources_count"] = len(sources)
        except Exception:
            cfg["signal_sources_count"] = 0
        return cfg

    @app.post("/api/system/config", tags=["System"])
    async def update_config(body: dict) -> dict:
        cfg = _load_runtime_config()
        allowed = {"content_confidence_threshold", "content_max_per_cycle", "groq_model"}
        for k, v in body.items():
            if k in allowed:
                cfg[k] = v
        _save_runtime_config(cfg)
        return cfg

    # ── Signal sources management ─────────────────────────────────────────────
    @app.get("/api/sources", tags=["System"])
    async def get_sources() -> dict:
        sources_path = os.path.join(_PROJECT_ROOT, "signal_sources.json")
        try:
            with open(sources_path) as f:
                data = json.load(f)
            # data may be a list (flat) or {"sources": [...]} (wrapped)
            sources = data.get("sources", data) if isinstance(data, dict) else data
            return {"sources": sources}
        except FileNotFoundError:
            return {"sources": []}

    @app.post("/api/sources", tags=["System"])
    async def update_sources(body: dict) -> dict:
        sources = body.get("sources", [])
        sources_path = os.path.join(_PROJECT_ROOT, "signal_sources.json")
        with open(sources_path, "w") as f:
            json.dump(sources, f, indent=2)
        return {"sources": sources, "count": len(sources)}

    # ── Database browser ──────────────────────────────────────────────────────
    @app.get("/api/db/browse", tags=["System"])
    async def db_browse(table: str = "signals", limit: int = 50) -> dict:
        allowed_tables = {"signals", "insights", "content", "distribution_queue",
                          "metrics", "posts", "schema_version", "schedule_preferences",
                          "engagement_log", "influencer_targets", "author_metrics"}
        if table not in allowed_tables:
            raise HTTPException(status_code=422, detail=f"Table '{table}' not allowed")
        from blogpilot.db.connection import get_connection
        try:
            with get_connection() as conn:
                conn.row_factory = None
                cur = conn.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,))
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            return {"table": table, "columns": cols, "rows": rows, "count": len(rows)}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ── Content update ────────────────────────────────────────────────────────
    @app.put("/api/content/{content_id}", tags=["Content"])
    async def update_content(content_id: int, body: dict) -> dict:
        import blogpilot.db.repositories.content as content_repo
        item = content_repo.get_by_id(content_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Content {content_id} not found")
        from blogpilot.db.connection import get_connection
        updates = {}
        if "body" in body:
            updates["body"] = body["body"]
        if "hashtags" in body:
            updates["hashtags"] = body["hashtags"]
        if "status" in body:
            updates["status"] = body["status"]
        if not updates:
            raise HTTPException(status_code=422, detail="No updatable fields provided")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [content_id]
        with get_connection() as conn:
            conn.execute(f"UPDATE content SET {set_clause} WHERE id = ?", values)
            conn.commit()
        return {"id": content_id, "updated": list(updates.keys())}

    # ── Pipeline run (selected steps) ─────────────────────────────────────────
    @app.post("/api/pipeline/run", tags=["System"])
    async def pipeline_run(body: dict) -> dict:
        steps = body.get("steps")  # list of ints 1-7, or None = all
        dry_run = body.get("dry_run", False)
        try:
            from automation.pipeline import run as pipeline_run_fn
            result = pipeline_run_fn(dry_run=dry_run, steps=steps)
            return result
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ── Daily content pipeline ─────────────────────────────────────────────────
    @app.post("/api/pipeline/daily", tags=["System"])
    async def daily_pipeline(body: dict) -> dict:
        """Research → pick topic → generate blog + LinkedIn → publish."""
        import asyncio
        topic = body.get("topic") or None
        content_types = body.get("content_types", ["blog_and_linkedin"])
        publish = body.get("publish", True)
        dry_run = body.get("dry_run", False)
        try:
            from automation.daily_pipeline import run as daily_run
            result = await asyncio.to_thread(
                daily_run,
                topic=topic,
                content_types=content_types,
                publish=publish,
                dry_run=dry_run,
            )
            return result
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ── Research endpoints ─────────────────────────────────────────────────────
    @app.post("/api/research/run", tags=["Research"])
    async def research_run(body: dict | None = None) -> dict:
        """Run topic research (Reddit + LinkedIn synthesis). Returns topic list."""
        import asyncio
        subreddits = (body or {}).get("subreddits") or None
        include_linkedin = (body or {}).get("include_linkedin", True)
        try:
            from topic_researcher import run_research
            topics = await asyncio.to_thread(
                run_research,
                subreddits=subreddits,
                include_linkedin=include_linkedin,
            )
            from datetime import datetime as _dt
            return {"topics": topics, "count": len(topics), "timestamp": _dt.now().isoformat()}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/research/topics", tags=["Research"])
    async def research_topics() -> dict:
        """Return the latest saved research topics."""
        try:
            from topic_researcher import load_saved_research, get_last_run_date
            topics = load_saved_research()
            return {
                "topics": topics,
                "count": len(topics),
                "last_run": get_last_run_date(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ── Scheduler config endpoints ─────────────────────────────────────────────
    @app.get("/api/schedule/config", tags=["Schedule"])
    async def get_schedule_config() -> dict:
        """Return the current smart_scheduler configuration."""
        try:
            from smart_scheduler import load_config
            return load_config()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/schedule/config", tags=["Schedule"])
    async def set_schedule_config(body: dict) -> dict:
        """Update smart_scheduler configuration and persist to scheduler_config.json."""
        try:
            from smart_scheduler import load_config, save_config
            cfg = load_config()
            allowed = {
                "enabled", "slots", "mode", "manual_id",
                "dry_run", "days", "day_content_type",
            }
            for key in allowed:
                if key in body:
                    cfg[key] = body[key]
            save_config(cfg)
            return {"saved": True, "config": cfg}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ── Scheduler control endpoints ────────────────────────────────────────────

    @app.get("/api/schedule/status", tags=["Schedule"])
    async def get_schedule_status() -> dict:
        """Return current scheduler running state, paused state, and next fire time."""
        try:
            from smart_scheduler import is_running, is_paused, load_config, get_next_fire
            running = is_running()
            paused = is_paused()
            cfg = load_config()
            next_dt = get_next_fire(cfg) if running and not paused else None
            return {
                "running": running,
                "paused": paused,
                "enabled": cfg.get("enabled", False),
                "next_fire": next_dt.isoformat() if next_dt else None,
                "dry_run": cfg.get("dry_run", False),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/schedule/start", tags=["Schedule"])
    async def start_schedule() -> dict:
        """Enable and start the content scheduler thread."""
        try:
            from smart_scheduler import start_scheduler, is_running, load_config, save_config
            cfg = load_config()
            cfg["enabled"] = True
            save_config(cfg)
            if not is_running():
                start_scheduler()
            return {"action": "started", "running": is_running()}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/schedule/stop", tags=["Schedule"])
    async def stop_schedule() -> dict:
        """Stop the content scheduler thread and disable it in config."""
        try:
            from smart_scheduler import stop_scheduler, is_running, load_config, save_config
            cfg = load_config()
            cfg["enabled"] = False
            save_config(cfg)
            stop_scheduler()
            return {"action": "stopped", "running": is_running()}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/schedule/pause", tags=["Schedule"])
    async def pause_schedule() -> dict:
        """Pause the content scheduler (thread stays alive, skips firing)."""
        try:
            from smart_scheduler import pause_scheduler, is_running, is_paused
            pause_scheduler()
            return {"action": "paused", "running": is_running(), "paused": is_paused()}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/schedule/resume", tags=["Schedule"])
    async def resume_schedule() -> dict:
        """Resume a paused content scheduler."""
        try:
            from smart_scheduler import resume_scheduler, is_running, is_paused
            resume_scheduler()
            return {"action": "resumed", "running": is_running(), "paused": is_paused()}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ── Mount web GUI ─────────────────────────────────────────────────────────
    try:
        from api.web_gui import router as web_gui_router
        app.include_router(web_gui_router, tags=["WebGUI"])
    except Exception as _wg_exc:
        logger.warning("Web GUI not available: %s", _wg_exc)

    # Signal Engine
    from blogpilot.signal_engine.router import router as signal_router
    app.include_router(signal_router, prefix="/api/signals", tags=["Signals"])

    # Insight Engine
    from blogpilot.insight_engine.router import router as insight_router
    app.include_router(insight_router, prefix="/api/insights", tags=["Insights"])

    # Content Engine
    from blogpilot.content_engine.router import router as content_router
    app.include_router(content_router, prefix="/api/content", tags=["Content"])

    # Distribution Engine
    from blogpilot.distribution_engine.router import router as dist_router
    app.include_router(dist_router, prefix="/api/distribution", tags=["Distribution"])

    # Analytics Engine
    from blogpilot.analytics_engine.router import router as analytics_router
    app.include_router(analytics_router, prefix="/api/analytics", tags=["Analytics"])

    # Engagement Engine (LinkedIn Growth)
    try:
        from blogpilot.engagement_engine.router import router as engagement_router
        app.include_router(engagement_router, prefix="/api/engagement", tags=["Engagement"])
    except Exception as _eng_exc:
        logger.warning("Engagement engine router not available: %s", _eng_exc)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    from blogpilot.config.settings import get_settings

    settings = get_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level="info",
    )
