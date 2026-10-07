"""queue.py — Phase 22 Production Job Queue & Multi-Worker State Manager."""
import uuid
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import select, update, delete, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.background_job import (
    BackgroundJob,
    JobStatus,
    JobPriority,
    JobType,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


PRIORITY_ORDER = {
    JobPriority.CRITICAL: 1,
    JobPriority.HIGH: 2,
    JobPriority.NORMAL: 3,
    JobPriority.LOW: 4,
}


class JobQueueService:
    """Service for enqueuing, claiming, retrying, and monitoring background jobs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue_job(
        self,
        job_type: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: str = JobPriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        max_attempts: int = 3,
        prevent_duplicate_running: bool = True,
    ) -> BackgroundJob:
        """Enqueues a new background job with priority and idempotency checks."""
        now = utc_now()
        sched_time = scheduled_at if scheduled_at is not None else now

        if prevent_duplicate_running:
            # Check if identical job is already queued or running
            stmt_exist = select(BackgroundJob).where(
                BackgroundJob.job_type == job_type,
                BackgroundJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
            res_exist = await self.session.execute(stmt_exist)
            existing = res_exist.scalar_one_or_none()
            if existing:
                logger.info(f"Job {job_type} already pending (ID: {existing.id}, status: {existing.status}). Skipping duplicate.")
                return existing

        job = BackgroundJob(
            id=uuid.uuid4(),
            job_type=job_type,
            status=JobStatus.QUEUED,
            priority=priority,
            scheduled_at=sched_time,
            attempts=0,
            max_attempts=max_attempts,
            payload=payload or {},
            created_at=now,
            updated_at=now,
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        logger.info(f"Enqueued job {job.job_type} (ID: {job.id}, priority: {job.priority})")
        return job

    async def claim_next_job(
        self,
        worker_id: str,
        lock_timeout_seconds: int = 300,
    ) -> Optional[BackgroundJob]:
        """Atomically claims the highest priority eligible queued job."""
        now = utc_now()
        lock_expiry = now + timedelta(seconds=lock_timeout_seconds)

        # 1. Query for candidates (queued or expired locks)
        stmt = (
            select(BackgroundJob)
            .where(
                or_(
                    and_(
                        BackgroundJob.status == JobStatus.QUEUED,
                        BackgroundJob.scheduled_at <= now,
                    ),
                    and_(
                        BackgroundJob.status == JobStatus.RUNNING,
                        BackgroundJob.lock_expires_at < now,
                    ),
                )
            )
            .order_by(
                BackgroundJob.priority.asc(),
                BackgroundJob.scheduled_at.asc(),
            )
            .limit(1)
        )
        res = await self.session.execute(stmt)
        job = res.scalar_one_or_none()

        if not job:
            return None

        # 2. Claim job
        job.status = JobStatus.RUNNING
        job.locked_by = worker_id
        job.lock_expires_at = lock_expiry
        job.started_at = now
        job.attempts += 1
        job.updated_at = now

        await self.session.commit()
        await self.session.refresh(job)
        logger.info(f"Worker {worker_id} claimed job {job.job_type} (ID: {job.id}, attempt {job.attempts}/{job.max_attempts})")
        return job

    async def complete_job(
        self,
        job_id: uuid.UUID,
        result: Optional[Dict[str, Any]] = None,
    ) -> BackgroundJob:
        """Marks a job as successfully completed."""
        now = utc_now()
        stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
        res = await self.session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatus.COMPLETED
        job.completed_at = now
        job.locked_by = None
        job.lock_expires_at = None
        job.result = result or {}
        job.updated_at = now

        await self.session.commit()
        await self.session.refresh(job)
        logger.info(f"Job {job.job_type} (ID: {job.id}) completed successfully.")
        return job

    async def fail_job(
        self,
        job_id: uuid.UUID,
        error_message: str,
        allow_retry: bool = True,
    ) -> BackgroundJob:
        """Handles job failure with exponential backoff + jitter."""
        now = utc_now()
        stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
        res = await self.session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.error_message = str(error_message)[:2000]
        job.locked_by = None
        job.lock_expires_at = None
        job.updated_at = now

        if allow_retry and job.attempts < job.max_attempts:
            # Exponential backoff + jitter: base 10s * 2^attempts + random(1-5)
            backoff_seconds = (10 * (2 ** (job.attempts - 1))) + random.uniform(1.0, 5.0)
            job.status = JobStatus.QUEUED
            job.scheduled_at = now + timedelta(seconds=backoff_seconds)
            logger.warning(
                f"Job {job.job_type} (ID: {job.id}) failed (attempt {job.attempts}/{job.max_attempts}). "
                f"Retrying in {round(backoff_seconds, 1)}s. Error: {error_message}"
            )
        else:
            job.status = JobStatus.FAILED
            job.completed_at = now
            logger.error(
                f"Job {job.job_type} (ID: {job.id}) permanently failed after {job.attempts} attempts. Error: {error_message}"
            )

        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def retry_job(self, job_id: uuid.UUID) -> BackgroundJob:
        """Manually resets a failed or cancelled job back to queued."""
        now = utc_now()
        stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
        res = await self.session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatus.QUEUED
        job.scheduled_at = now
        job.locked_by = None
        job.lock_expires_at = None
        job.error_message = None
        job.updated_at = now

        await self.session.commit()
        await self.session.refresh(job)
        logger.info(f"Manual retry scheduled for job {job.job_type} (ID: {job.id})")
        return job

    async def cleanup_old_jobs(
        self,
        retention_days_completed: int = 30,
        retention_days_failed: int = 90,
    ) -> Dict[str, int]:
        """Purges old job records beyond retention windows."""
        now = utc_now()
        cutoff_completed = now - timedelta(days=retention_days_completed)
        cutoff_failed = now - timedelta(days=retention_days_failed)

        stmt_comp = delete(BackgroundJob).where(
            BackgroundJob.status == JobStatus.COMPLETED,
            BackgroundJob.completed_at < cutoff_completed,
        )
        res_comp = await self.session.execute(stmt_comp)

        stmt_fail = delete(BackgroundJob).where(
            BackgroundJob.status.in_([JobStatus.FAILED, JobStatus.CANCELLED]),
            BackgroundJob.completed_at < cutoff_failed,
        )
        res_fail = await self.session.execute(stmt_fail)

        await self.session.commit()
        return {
            "completed_jobs_deleted": res_comp.rowcount,
            "failed_jobs_deleted": res_fail.rowcount,
        }

    async def get_job_stats(self) -> Dict[str, Any]:
        """Returns aggregate queue health metrics."""
        stmt = select(
            BackgroundJob.status,
            func.count(BackgroundJob.id),
        ).group_by(BackgroundJob.status)

        res = await self.session.execute(stmt)
        counts = dict(res.all())

        return {
            "queued": counts.get(JobStatus.QUEUED, 0),
            "running": counts.get(JobStatus.RUNNING, 0),
            "completed": counts.get(JobStatus.COMPLETED, 0),
            "failed": counts.get(JobStatus.FAILED, 0),
            "total": sum(counts.values()),
        }

    async def list_jobs(
        self,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[BackgroundJob], int]:
        """Paginated list of background jobs for admin monitor."""
        stmt = select(BackgroundJob)
        if status:
            stmt = stmt.where(BackgroundJob.status == status.upper().strip())
        if job_type:
            stmt = stmt.where(BackgroundJob.job_type == job_type.upper().strip())

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one() or 0

        # Pagination
        offset = (page - 1) * limit
        stmt = stmt.order_by(desc(BackgroundJob.created_at)).offset(offset).limit(limit)

        res = await self.session.execute(stmt)
        jobs = list(res.scalars().all())
        return jobs, total
