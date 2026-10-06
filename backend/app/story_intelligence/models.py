"""models.py — Phase 16 Multi-Source Story Intelligence Domain Models."""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
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
    from app.models.article import Article
    from app.models.topic import Topic


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(350), unique=True, index=True, nullable=False
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="ACTIVE", index=True, nullable=False
    )  # ACTIVE | DEVELOPING | STABLE | RESOLVED | ARCHIVED
    first_published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    primary_topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    importance_score: Mapped[float] = mapped_column(
        Float, default=0.5, index=True, nullable=False
    )
    quality_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    article_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    independent_source_count: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    activity_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    primary_article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
    )
    latest_article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
    )

    merged_into_story_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    merged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    primary_topic: Mapped[Optional["Topic"]] = relationship("Topic")
    primary_article: Mapped[Optional["Article"]] = relationship(
        "Article", foreign_keys=[primary_article_id]
    )
    latest_article: Mapped[Optional["Article"]] = relationship(
        "Article", foreign_keys=[latest_article_id]
    )
    story_articles: Mapped[List["StoryArticle"]] = relationship(
        "StoryArticle",
        back_populates="story",
        cascade="all, delete-orphan",
        order_by="StoryArticle.added_at",
    )


class StoryArticle(Base):
    __tablename__ = "story_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(
        String(30), default="PRIMARY", nullable=False
    )  # PRIMARY | UPDATE | ANALYSIS | REACTION | BACKGROUND | RELATED
    similarity_score: Mapped[float] = mapped_column(
        Float, default=1.0, nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    story: Mapped["Story"] = relationship("Story", back_populates="story_articles")
    article: Mapped["Article"] = relationship("Article")

    __table_args__ = (
        UniqueConstraint("story_id", "article_id", name="uq_story_article"),
    )


class StoryMergeEvent(Base):
    __tablename__ = "story_merge_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    similarity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    merged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
