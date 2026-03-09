"""Phoenix Marketing Intelligence Engine — Full Automation Pipeline.

Runs all seven engine steps in sequence. Each step is fully isolated —
a failure in one step logs the error and continues to the next.

Usage:
    python automation/pipeline.py              # single run
    python automation/pipeline.py --schedule   # run + APScheduler (every 24h)
    python automation/pipeline.py --dry-run    # log steps without executing
    python automation/pipeline.py --interval 6 --schedule

Pipeline steps:
    1. Collect Signals
    2. Generate Insights
    3. Generate Content
    4. Schedule Distribution   ← plan + queue new content for publishing
    5. Publish Content         ← distribution worker processes due jobs
    6. Collect Analytics       ← fetch LinkedIn/GA metrics
    7. Update Feedback Signals ← performance scores + schedule preferences
"""

from __future__ import annotations

import argparse
import logging
import sys
import os
from datetime import datetime

# Ensure BlogMarketing root is importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PIPELINE] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pipeline")

# --------------------------------------------------------------------------
# State tracking (in-memory; readable via GET /api/system/status)
# --------------------------------------------------------------------------

_state: dict = {
    "last_run": None,
    "signals_collected": 0,
    "insights_generated": 0,
    "content_created": 0,
    "content_scheduled": 0,
    "jobs_published": 0,
    "metrics_collected": 0,
    "feedback_updated": False,
    "elapsed_seconds": 0.0,
}


def _step(name: str, fn, dry_run: bool = False) -> dict:
    """Execute one pipeline step with full error isolation."""
    logger.info("── Step: %s", name)
    if dry_run:
        logger.info("   [DRY RUN] skipped.")
        return {}
    try:
        result = fn()
        logger.info("   ✓ %s complete: %s", name, result)
        return result or {}
    except Exception as exc:
        logger.error("   ✗ %s failed: %s", name, exc)
        return {"error": str(exc)}


# --------------------------------------------------------------------------
# Step functions
# --------------------------------------------------------------------------

def _collect_signals() -> dict:
    """Step 1: Fetch and score new signals from all configured sources."""
    from blogpilot.signal_engine.workers.signal_worker import run_now
    return run_now()


def _generate_insights() -> dict:
    """Step 2: Cluster signals and synthesise insights via Groq."""
    from blogpilot.insight_engine.workers.insight_worker import run_now
    return run_now()


def _generate_content() -> dict:
    """Step 3: Generate blog posts and LinkedIn content from approved insights."""
    from blogpilot.content_engine.workers.content_worker import run_now
    return run_now()


def _schedule_distribution() -> dict:
    """Step 4: Queue all newly generated draft content for publishing.

    Finds content with status='draft' that has no distribution_queue entry,
    runs the distribution planner on each, and inserts queue jobs.
    """
    import blogpilot.db.repositories.content as content_repo
    import blogpilot.db.repositories.distribution as dist_repo
    from blogpilot.distribution_engine.services.distribution_planner import plan
    from blogpilot.distribution_engine.models.distribution_queue_model import DistributionQueue

    # Get all draft content
    drafts = content_repo.get_all(status="draft", limit=50)

    # Get content_ids already in the queue to avoid duplicates
    queued_ids = {item.content_id for item in dist_repo.get_all(limit=500)}

    scheduled = 0
    for c in drafts:
        if c.id in queued_ids:
            continue
        try:
            jobs = plan(content_type=c.content_type, content_id=c.id)
            for job in jobs:
                item = DistributionQueue(
                    content_id=job["content_id"],
                    channel=job["channel"],
                    scheduled_time=job["scheduled_time"],
                    status="scheduled" if job["scheduled_time"] else "queued",
                )
                dist_repo.insert(item)
                scheduled += 1
        except Exception as exc:
            logger.warning("Could not schedule content %d: %s", c.id, exc)

    return {"content_scheduled": scheduled}


def _publish_content() -> dict:
    """Step 5: Process all due distribution queue items."""
    from blogpilot.distribution_engine.workers.distribution_worker import run_now
    return run_now()


def _collect_analytics() -> dict:
    """Step 6: Fetch LinkedIn and website performance metrics."""
    from blogpilot.analytics_engine.workers.analytics_worker import run_now
    return run_now()


def _update_feedback() -> dict:
    """Step 7: Recompute performance scores and update schedule_preferences.

    This closes the feedback loop — best posting times and top topics flow
    back into the Distribution Planner and Content Planner on the next run.
    """
    from blogpilot.analytics_engine.services.performance_analyzer import analyze
    return analyze()


def _run_engagement() -> dict:
    """Step 8 (optional): Run LinkedIn engagement cycle.

    Only active when ENABLE_ENGAGEMENT=true is set in the environment.
    """
    import os
    if os.environ.get("ENABLE_ENGAGEMENT", "").lower() != "true":
        logger.info("   Step 8 skipped — set ENABLE_ENGAGEMENT=true to enable.")
        return {"skipped": True, "reason": "ENABLE_ENGAGEMENT not set"}
    from blogpilot.engagement_engine.workers.engagement_worker import run_now
    return run_now()


# --------------------------------------------------------------------------
# Main pipeline run
# --------------------------------------------------------------------------

def run(dry_run: bool = False, steps: list[int] | None = None) -> dict:
    """Execute one full pipeline cycle.

    Args:
        dry_run: Log steps without executing.
        steps: Optional list of step numbers (1-8) to run. Runs 1-7 if None.
               Step 8 (LinkedIn Engagement) only executes when ENABLE_ENGAGEMENT=true.

    Returns:
        Summary dict with step counts and elapsed time.
    """
    _steps = set(steps) if steps else set(range(1, 8))
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info("Phoenix Pipeline Starting  --  %s", start.strftime("%Y-%m-%d %H:%M:%S UTC"))
    logger.info("Steps: %s", sorted(_steps))
    logger.info("=" * 60)

    # 1. Signals
    r1 = _step("1/7  Collect Signals", _collect_signals, dry_run) if 1 in _steps else {}
    signals_new = r1.get("signals_new", 0) + r1.get("signals_scored", 0)

    # 2. Insights
    r2 = _step("2/7  Generate Insights", _generate_insights, dry_run) if 2 in _steps else {}
    insights_gen = r2.get("insights_created", 0)

    # 3. Content
    r3 = _step("3/7  Generate Content", _generate_content, dry_run) if 3 in _steps else {}
    content_created = r3.get("content_created", 0)

    # 4. Schedule
    r4 = _step("4/7  Schedule Distribution", _schedule_distribution, dry_run) if 4 in _steps else {}
    content_scheduled = r4.get("content_scheduled", 0)

    # 5. Publish
    r5 = _step("5/7  Publish Content", _publish_content, dry_run) if 5 in _steps else {}
    jobs_published = r5.get("jobs_published", 0)

    # 6. Analytics
    r6 = _step("6/7  Collect Analytics", _collect_analytics, dry_run) if 6 in _steps else {}
    metrics = r6.get("linkedin_collected", 0) + r6.get("website_collected", 0)

    # 7. Feedback
    r7 = _step("7/7  Update Feedback Signals", _update_feedback, dry_run) if 7 in _steps else {}
    feedback_ok = "error" not in r7

    # 8. LinkedIn Engagement (optional, gated by ENABLE_ENGAGEMENT=true)
    r8 = _step("8/8  LinkedIn Engagement", _run_engagement, dry_run) if 8 in _steps else {}
    engagement_posts = r8.get("posts_engaged", 0)

    elapsed = round((datetime.utcnow() - start).total_seconds(), 1)

    summary = {
        "last_run": start.isoformat() + "Z",
        "signals_collected": signals_new,
        "insights_generated": insights_gen,
        "content_created": content_created,
        "content_scheduled": content_scheduled,
        "jobs_published": jobs_published,
        "metrics_collected": metrics,
        "feedback_updated": feedback_ok,
        "engagement_posts": engagement_posts,
        "elapsed_seconds": elapsed,
    }

    _state.update(summary)

    logger.info("=" * 60)
    logger.info("Pipeline Complete in %.1fs", elapsed)
    logger.info(
        "  Signals %-3d | Insights %-3d | Content %-3d | Scheduled %-3d | "
        "Published %-3d | Metrics %-3d | Feedback %s",
        signals_new, insights_gen, content_created, content_scheduled,
        jobs_published, metrics, "OK" if feedback_ok else "FAIL",
    )
    logger.info("=" * 60)

    return summary


def get_status() -> dict:
    """Return last pipeline run state — used by GET /api/system/status."""
    return dict(_state)


# --------------------------------------------------------------------------
# Scheduled execution
# --------------------------------------------------------------------------

def start_scheduler(interval_hours: int = 24) -> None:
    """Start a blocking APScheduler that runs the pipeline on a fixed interval.

    Executes one run immediately on startup, then repeats every interval_hours.
    """
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler  # type: ignore[import]
    except ImportError:
        logger.error("APScheduler not installed — run: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run, trigger="interval", hours=interval_hours, id="pipeline", replace_existing=True,
    )
    logger.info(
        "Scheduler started — pipeline runs every %d hour(s). Ctrl+C to stop.", interval_hours
    )

    # Run immediately at startup
    run()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Pipeline scheduler stopped.")


# --------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Phoenix Marketing Intelligence Engine — Automation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="Run on a recurring schedule (blocking — use for background automation)",
    )
    parser.add_argument(
        "--interval", type=int, default=24, metavar="HOURS",
        help="Schedule interval in hours (default: 24)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Log all steps without executing any engine code",
    )
    args = parser.parse_args()

    if args.schedule:
        start_scheduler(interval_hours=args.interval)
    else:
        result = run(dry_run=args.dry_run)
        if not args.dry_run:
            print("\nSummary:", result)
