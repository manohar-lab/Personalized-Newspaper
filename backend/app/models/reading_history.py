"""reading_history.py — Phase 12 Aggregate Reading History Model.

Maintains aggregate reading behavior per user + article to track engagement intelligence,
completion milestones, and consumption patterns.
"""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, UUID, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.article import Article


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReadingHistory(Base):
    __tablename__ = "reading_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    open_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_scroll_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    average_scroll_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completion_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_completion_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    engagement_level: Mapped[str] = mapped_column(
        String(20), default="BOUNCED", nullable=False, index=True
    )  # BOUNCED | LOW | MEDIUM | HIGH | DEEP
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="reading_history")
    article: Mapped["Article"] = relationship("Article", backref="reading_history")

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_user_article_reading_history"),
        Index("ix_reading_history_user_last_read", "user_id", "last_read_at"),
    )
