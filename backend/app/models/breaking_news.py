"""breaking_news.py — Phase 22 Breaking News Detection & Events Model."""
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Float,
    ForeignKey,
    UUID,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.story_intelligence.models import Story


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BreakingNewsStatus:
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class BreakingNewsEvent(Base):
    __tablename__ = "breaking_news_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    importance: Mapped[float] = mapped_column(
        Float, default=0.90, index=True, nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=BreakingNewsStatus.ACTIVE, index=True, nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    story: Mapped["Story"] = relationship("Story", backref="breaking_events")

    __table_args__ = (
        Index("ix_breaking_status_importance", "status", "importance"),
    )
