"""pipeline_run.py — Phase 10 Autonomous Pipeline Run Model."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # FETCH_FEEDS | EXTRACT_PENDING | ANALYZE_PENDING | GENERATE_EDITIONS | CLEANUP_OLD_DATA | FULL_PIPELINE
    status: Mapped[str] = mapped_column(
        String(20), default="RUNNING", index=True, nullable=False
    )  # RUNNING | SUCCESS | PARTIAL | FAILED
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    items_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
