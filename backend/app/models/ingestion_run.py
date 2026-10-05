import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.feed import NewsFeed

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_feeds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="RUNNING", index=True, nullable=False
    )  # RUNNING | SUCCESS | PARTIAL | FAILED
    articles_fetched: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    articles_created: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    duplicates_found: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    errors_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    feed: Mapped["NewsFeed"] = relationship("NewsFeed", back_populates="runs")
