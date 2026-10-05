"""scheduler.py — Phase 10 Production APScheduler Background Worker Service."""
import logging
from typing import Any, Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.workers.jobs import (
    job_fetch_feeds,
    job_extract_pending,
    job_analyze_pending,
    job_generate_daily_editions,
    job_cleanup_old_data,
)

logger = logging.getLogger(__name__)

# Module-level singleton
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Returns the active scheduler singleton, if started."""
    return _scheduler


def start_scheduler() -> AsyncIOScheduler:
    """
    Initializes and starts the authoritative AsyncIOScheduler instance with all autonomous jobs.
    Ensures idempotent singleton initialization (exactly one authoritative scheduler).
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.info("APScheduler is already running.")
        return _scheduler

    logger.info("Initializing APScheduler for Autonomous News Pipeline...")
    _scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)

    # 1. News Fetching Job
    _scheduler.add_job(
        job_fetch_feeds,
        trigger=IntervalTrigger(minutes=settings.NEWS_FETCH_INTERVAL_MINUTES),
        id="job_fetch_feeds",
        name="Fetch RSS/Atom Feeds",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 2. Web Article Extraction Job
    _scheduler.add_job(
        job_extract_pending,
        trigger=IntervalTrigger(minutes=settings.ARTICLE_EXTRACTION_INTERVAL_MINUTES),
        id="job_extract_pending",
        name="Extract Pending Article Content",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 3. AI Analysis & Embedding Job
    _scheduler.add_job(
        job_analyze_pending,
        trigger=IntervalTrigger(minutes=settings.ARTICLE_ANALYSIS_INTERVAL_MINUTES),
        id="job_analyze_pending",
        name="AI Analyze Pending Articles",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 4. Daily Edition Generation Job
    _scheduler.add_job(
        job_generate_daily_editions,
        trigger=CronTrigger(
            hour=settings.EDITION_GENERATION_HOUR,
            minute=0,
            timezone=settings.DEFAULT_TIMEZONE,
        ),
        id="job_generate_daily_editions",
        name="Generate Daily Personalized Editions",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 5. Cleanup Job
    _scheduler.add_job(
        job_cleanup_old_data,
        trigger=IntervalTrigger(hours=settings.CLEANUP_INTERVAL_HOURS),
        id="job_cleanup_old_data",
        name="Cleanup Old Pipeline Data",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    _scheduler.start()
    logger.info(
        f"APScheduler started successfully with {len(_scheduler.get_jobs())} jobs: "
        f"fetch={settings.NEWS_FETCH_INTERVAL_MINUTES}m, "
        f"extract={settings.ARTICLE_EXTRACTION_INTERVAL_MINUTES}m, "
        f"analyze={settings.ARTICLE_ANALYSIS_INTERVAL_MINUTES}m, "
        f"editions={settings.EDITION_GENERATION_HOUR}:00 [{settings.DEFAULT_TIMEZONE}], "
        f"cleanup={settings.CLEANUP_INTERVAL_HOURS}h."
    )
    return _scheduler


async def stop_scheduler() -> None:
    """Gracefully shuts down the scheduler, waiting for in-flight tasks to complete."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.info("Shutting down APScheduler...")
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler shutdown complete.")


def get_scheduler_status() -> Dict[str, Any]:
    """Returns runtime status and registered jobs metadata for health and admin endpoints."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        return {
            "status": "stopped",
            "running": False,
            "jobs_count": 0,
            "jobs": [],
        }

    jobs_info: List[Dict[str, Any]] = []
    for j in _scheduler.get_jobs():
        jobs_info.append({
            "id": j.id,
            "name": j.name,
            "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
            "trigger": str(j.trigger),
        })

    return {
        "status": "running",
        "running": True,
        "jobs_count": len(jobs_info),
        "jobs": jobs_info,
    }
