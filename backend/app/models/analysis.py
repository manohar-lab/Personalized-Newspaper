import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List, Any
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    DateTime,
    ForeignKey,
    UUID,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.article import Article

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ArticleKeyword(Base):
    __tablename__ = "article_keywords"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    article: Mapped["Article"] = relationship("Article", back_populates="keywords")


class ArticleAnalysis(Base):
    __tablename__ = "article_analysis"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    primary_category: Mapped[Optional[str]] = mapped_column(
        String(50), index=True, nullable=True
    )  # TECHNOLOGY | SCIENCE | BUSINESS | FINANCE | WORLD | POLITICS | HEALTH | EDUCATION | SPORTS | ENTERTAINMENT | OTHER
    article_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # NEWS | ANALYSIS | OPINION | TUTORIAL | RESEARCH | PRODUCT | ANNOUNCEMENT | INTERVIEW | REVIEW | OTHER
    importance_score: Mapped[float] = mapped_column(
        Float, default=0.5, nullable=False
    )  # 0.0 to 1.0 (General importance/significance)
    article_quality_score: Mapped[float] = mapped_column(
        Float, default=0.5, nullable=False
    )  # 0.0 to 1.0 (Content completeness, extraction quality, readability, metadata)
    quality_breakdown: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    analysis_version: Mapped[str] = mapped_column(
        String(20), default="v1", nullable=False
    )
    analysis_status: Mapped[str] = mapped_column(
        String(30), default="NOT_ANALYZED", index=True, nullable=False
    )  # NOT_ANALYZED | PENDING | PROCESSING | SUCCESS | FAILED
    analysis_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analysis_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Embedding vector representation
    embedding: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    embedded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    article: Mapped["Article"] = relationship("Article", back_populates="analysis")
