"""background_job.py — Phase 22 Production Job Queue & State Tracking Model."""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    JSON,
    UUID,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobPriority:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class JobType:
    FETCH_FEEDS = "FETCH_FEEDS"
    EXTRACT_ARTICLES = "EXTRACT_ARTICLES"
    ANALYZE_ARTICLES = "ANALYZE_ARTICLES"
    UPDATE_STORIES = "UPDATE_STORIES"
    UPDATE_USER_INTERESTS = "UPDATE_USER_INTERESTS"
    GENERATE_EDITIONS = "GENERATE_EDITIONS"
    REFRESH_EDITIONS = "REFRESH_EDITIONS"
    CLEANUP = "CLEANUP"
    HEALTH_CHECK = "HEALTH_CHECK"


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=JobStatus.QUEUED, index=True, nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(16), default=JobPriority.NORMAL, index=True, nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, default=3, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    locked_by: Mapped[Optional[str]] = mapped_column(
        String(128), index=True, nullable=True
    )
    lock_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_job_status_priority_scheduled", "status", "priority", "scheduled_at"),
        Index("ix_job_type_status", "job_type", "status"),
    )
