import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.source import NewsSource
    from app.models.feed import NewsFeed

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(
        String(50), default="FEED_INGESTION", nullable=False, index=True
    )  # FEED_INGESTION | ARTICLE_EXTRACTION | SOURCE_CRAWL | SYNDICATION_SYNC
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feed_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_feeds.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), default="QUEUED", nullable=False, index=True
    )  # QUEUED | RUNNING | COMPLETED | PARTIAL | FAILED
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    items_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optional relationships
    source: Mapped[Optional["NewsSource"]] = relationship("NewsSource")
    feed: Mapped[Optional["NewsFeed"]] = relationship("NewsFeed")
