import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import Column, String, Text, Boolean, DateTime, UUID, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.feed import NewsFeed
    from app.models.article import Article

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    website_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Phase 15 Quality & Reliability Metrics
    quality_score: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    quality_confidence: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    reliability_score: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    coverage_score: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    extraction_success_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    duplicate_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    health_status: Mapped[str] = mapped_column(String(32), default="HEALTHY", nullable=False)  # HEALTHY | DEGRADED | FAILING | INACTIVE
    last_evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluation_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    feeds: Mapped[List["NewsFeed"]] = relationship(
        "NewsFeed", back_populates="source", cascade="all, delete-orphan"
    )
    articles: Mapped[List["Article"]] = relationship(
        "Article", back_populates="source"
    )
