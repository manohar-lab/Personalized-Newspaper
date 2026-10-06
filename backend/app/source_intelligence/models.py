"""models.py — Phase 15 Source Intelligence, Health, Preference & Reporting Models."""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UUID,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.source import NewsSource
    from app.models.article import Article


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceHealthMetric(Base):
    """Daily aggregated health and ingestion performance metrics per news source."""
    __tablename__ = "source_health_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    date: Mapped[str] = mapped_column(
        String(10), index=True, nullable=False
    )  # YYYY-MM-DD
    fetch_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fetch_success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    article_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extraction_success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extraction_failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    source: Mapped["NewsSource"] = relationship("NewsSource")

    __table_args__ = (
        UniqueConstraint("source_id", "date", name="uq_source_health_date"),
    )


class UserSourcePreference(Base):
    """User preferences for following or muting specific news sources."""
    __tablename__ = "user_source_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    is_following: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship("User")
    source: Mapped["NewsSource"] = relationship("NewsSource")

    __table_args__ = (
        UniqueConstraint("user_id", "source_id", name="uq_user_source_pref"),
    )


class UserSourceAffinity(Base):
    """Implicit learned affinity for specific news sources based on reading behavior."""
    __tablename__ = "user_source_affinities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)  # 0.0 to 1.0
    confidence: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship("User")
    source: Mapped["NewsSource"] = relationship("NewsSource")

    __table_args__ = (
        UniqueConstraint("user_id", "source_id", name="uq_user_source_affinity"),
    )


class SourceReport(Base):
    """User reports regarding quality, paywall, or broken feeds of a news source."""
    __tablename__ = "source_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_sources.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reason: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # MISLEADING | LOW_QUALITY | BROKEN_ARTICLE | DUPLICATE | PAYWALL | OTHER
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False
    )  # PENDING | REVIEWED | RESOLVED | DISMISSED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    source: Mapped["NewsSource"] = relationship("NewsSource")
    user: Mapped[Optional["User"]] = relationship("User")


class ArticleReport(Base):
    """User reports regarding a specific article's quality, completeness, or paywall."""
    __tablename__ = "article_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reason: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # MISLEADING | LOW_QUALITY | BROKEN_ARTICLE | DUPLICATE | PAYWALL | OTHER
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False
    )  # PENDING | REVIEWED | RESOLVED | DISMISSED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    article: Mapped["Article"] = relationship("Article")
    user: Mapped[Optional["User"]] = relationship("User")
