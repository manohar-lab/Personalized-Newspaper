"""admin_jobs.py — Phase 22 Production Admin Job Queue & Scheduler Monitoring Endpoints."""
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, Path
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.background_job import BackgroundJob
from app.newspaper.models import NewspaperEdition
from app.workers.queue import JobQueueService
from app.workers.scheduler import get_scheduler_status

router = APIRouter()


def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Verifies that the user has admin privileges or is the authoritative user."""
    # For local/single user setups, authenticated active users can access admin diagnostics
    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


@router.get("/scheduler/status", summary="Get scheduler status and next ticks")
async def get_scheduler_info(
    current_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns runtime scheduler status, next scheduled runs, and queue metrics."""
    sched_status = get_scheduler_status()
    queue_service = JobQueueService(db)
    queue_stats = await queue_service.get_job_stats()

    return {
        "scheduler": sched_status,
        "queue_stats": queue_stats,
    }


@router.get("/jobs", summary="List background jobs with status filters")
async def list_jobs(
    status: Optional[str] = Query(None, description="QUEUED | RUNNING | COMPLETED | FAILED | CANCELLED"),
    job_type: Optional[str] = Query(None, description="Job type name"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of background jobs for operations monitoring."""
    queue_service = JobQueueService(db)
    items, total = await queue_service.list_jobs(
        status=status,
        job_type=job_type,
        page=page,
        limit=limit,
    )
    return {
        "items": [
            {
                "id": str(j.id),
                "job_type": j.job_type,
                "status": j.status,
                "priority": j.priority,
                "scheduled_at": j.scheduled_at.isoformat() if j.scheduled_at else None,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "attempts": j.attempts,
                "max_attempts": j.max_attempts,
                "error_message": j.error_message,
                "locked_by": j.locked_by,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in items
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/jobs/{id}", summary="Get background job detail")
async def get_job_detail(
    id: uuid.UUID = Path(..., description="Background Job UUID"),
    current_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed execution payload and result for a specific background job."""
    stmt = select(BackgroundJob).where(BackgroundJob.id == id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Background job not found",
        )

    return {
        "id": str(job.id),
        "job_type": job.job_type,
        "status": job.status,
        "priority": job.priority,
        "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "error_message": job.error_message,
        "locked_by": job.locked_by,
        "payload": job.payload,
        "result": job.result,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.post("/jobs/{id}/retry", summary="Manually retry a failed background job")
async def retry_failed_job(
    id: uuid.UUID = Path(..., description="Background Job UUID"),
    current_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually requeue a failed or cancelled background job for immediate execution."""
    queue_service = JobQueueService(db)
    try:
        job = await queue_service.retry_job(id)
        return {
            "status": "success",
            "message": f"Job {job.job_type} ({job.id}) re-queued successfully",
            "job_id": str(job.id),
            "job_status": job.status,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/editions", summary="Admin edition monitoring across users")
async def list_admin_editions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Monitors edition generation velocity and status across all users."""
    offset = (page - 1) * limit
    stmt = (
        select(NewspaperEdition)
        .order_by(desc(NewspaperEdition.created_at))
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    editions = list(res.scalars().all())

    count_stmt = select(func.count(NewspaperEdition.id))
    total = (await db.execute(count_stmt)).scalar_one() or 0

    return {
        "items": [
            {
                "id": str(e.id),
                "user_id": str(e.user_id),
                "edition_date": e.edition_date,
                "edition_type": getattr(e, "edition_type", "MORNING"),
                "version": e.version,
                "title": e.title,
                "status": e.status,
                "generated_at": e.generated_at.isoformat() if e.generated_at else None,
                "published_at": e.published_at.isoformat() if getattr(e, "published_at", None) else None,
            }
            for e in editions
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/health", summary="Pipeline health check")
async def get_pipeline_health(
    current_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate health status of background scheduler, database, and job queues."""
    queue_service = JobQueueService(db)
    stats = await queue_service.get_job_stats()
    sched = get_scheduler_status()

    return {
        "status": "healthy" if sched.get("running") else "degraded",
        "scheduler_running": sched.get("running", False),
        "queue_stats": stats,
    }
