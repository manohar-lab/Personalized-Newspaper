"""admin_pipeline.py — Phase 10 Admin Pipeline Monitoring and Manual Trigger Endpoints."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.news_pipeline_service import NewsPipelineService
from app.workers.scheduler import get_scheduler_status

router = APIRouter()


@router.get("/status", summary="Get comprehensive pipeline status and running jobs")
async def get_admin_pipeline_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Protected admin endpoint to inspect background scheduler status,
    most recent runs per job stage, and active running tasks.
    """
    service = NewsPipelineService(db)
    status_data = await service.get_pipeline_status()
    sched_info = get_scheduler_status()

    return {
        "scheduler": sched_info,
        "pipeline": status_data,
    }


@router.get("/runs", summary="List recent pipeline execution run logs")
async def get_pipeline_runs(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Lists recent pipeline run entries."""
    service = NewsPipelineService(db)
    return await service.get_recent_runs(limit=limit)


@router.post("/trigger/fetch", summary="Manually trigger news feed ingestion")
async def trigger_fetch_feeds(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Triggers immediate feed ingestion."""
    service = NewsPipelineService(db)
    return await service.run_fetch_feeds()


@router.post("/trigger/extract", summary="Manually trigger pending article extraction")
async def trigger_extract_articles(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Triggers immediate web extraction for pending articles."""
    service = NewsPipelineService(db)
    return await service.run_extract_pending_articles(limit=limit)


@router.post("/trigger/analyze", summary="Manually trigger pending AI article analysis")
async def trigger_analyze_articles(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Triggers immediate AI analysis for pending articles."""
    service = NewsPipelineService(db)
    return await service.run_analyze_pending_articles(limit=limit)


@router.post("/trigger/generate", summary="Manually trigger daily edition generation")
async def trigger_generate_editions(
    target_date: Optional[str] = Query(default=None, description="Optional YYYY-MM-DD date"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Triggers daily edition generation for all active users."""
    service = NewsPipelineService(db)
    return await service.run_generate_daily_editions(target_date=target_date)


@router.post("/trigger/cleanup", summary="Manually trigger pipeline log cleanup")
async def trigger_cleanup(
    retention_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Cleans up old pipeline runs."""
    service = NewsPipelineService(db)
    return await service.run_cleanup_old_data(retention_days=retention_days)


@router.post("/trigger/all", summary="Manually trigger full autonomous pipeline")
async def trigger_full_pipeline(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Executes the full pipeline in order: FETCH -> EXTRACT -> ANALYZE -> GENERATE."""
    service = NewsPipelineService(db)
    return await service.run_full_autonomous_pipeline()
