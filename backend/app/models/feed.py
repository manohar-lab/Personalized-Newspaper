import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.source import NewsSource
    from app.models.article import Article
    from app.models.ingestion_run import IngestionRun
    from app.models.topic import Topic

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NewsFeed(Base):
    __tablename__ = "news_feeds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    feed_url: Mapped[str] = mapped_column(String(1024), index=True, nullable=False)
    feed_type: Mapped[str] = mapped_column(
        String(20), default="RSS", nullable=False
    )  # RSS | ATOM
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    source: Mapped["NewsSource"] = relationship("NewsSource", back_populates="feeds")
    articles: Mapped[List["Article"]] = relationship(
        "Article", back_populates="feed"
    )
    runs: Mapped[List["IngestionRun"]] = relationship(
        "IngestionRun", back_populates="feed", cascade="all, delete-orphan"
    )
    default_topic: Mapped[Optional["Topic"]] = relationship("Topic")
