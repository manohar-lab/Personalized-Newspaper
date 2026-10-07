"""models.py — Phase 17 Persistent Newspaper Editions, Sections & Stories Models."""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
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
    from app.models.article import Article
    from app.story_intelligence.models import Story


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NewspaperEdition(Base):
    __tablename__ = "newspaper_editions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    edition_date: Mapped[str] = mapped_column(
        String(10), index=True, nullable=False
    )  # YYYY-MM-DD
    title: Mapped[str] = mapped_column(
        String(255), default="PERSONAL DAILY", nullable=False
    )
    subtitle: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    editorial_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="READY", index=True, nullable=False
    )  # GENERATING | READY | STALE | FAILED
    version: Mapped[int] = mapped_column(
        Integer, default=1, index=True, nullable=False
    )
    edition_type: Mapped[str] = mapped_column(
        String(30), default="MORNING", index=True, nullable=False
    )  # MORNING | MIDDAY | EVENING | BREAKING
    supersedes_edition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship("User", backref="newspaper_editions")
    sections: Mapped[List["NewspaperSection"]] = relationship(
        "NewspaperSection",
        back_populates="edition",
        cascade="all, delete-orphan",
        order_by="NewspaperSection.display_order",
    )
    stories: Mapped[List["NewspaperStory"]] = relationship(
        "NewspaperStory",
        back_populates="edition",
        cascade="all, delete-orphan",
        order_by="NewspaperStory.position",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "edition_date", "version", name="uq_user_edition_date_version"),
    )


class NewspaperSection(Base):
    __tablename__ = "newspaper_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("newspaper_editions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    section_type: Mapped[str] = mapped_column(
        String(50), default="TOP_STORIES", index=True, nullable=False
    )  # LEAD | TOP_STORIES | TECHNOLOGY | BUSINESS | SCIENCE | WORLD | INDIA | SPORTS | ENTERTAINMENT | DISCOVER | FOR_YOU
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    edition: Mapped["NewspaperEdition"] = relationship(
        "NewspaperEdition", back_populates="sections"
    )
    stories: Mapped[List["NewspaperStory"]] = relationship(
        "NewspaperStory",
        back_populates="section_rel",
        cascade="all, delete-orphan",
        order_by="NewspaperStory.position",
    )


class NewspaperStory(Base):
    __tablename__ = "newspaper_stories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("newspaper_editions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    story_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("newspaper_sections.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    editorial_role: Mapped[str] = mapped_column(
        String(30), default="STANDARD", nullable=False
    )  # LEAD | TOP_STORY | STANDARD | BRIEF | DISCOVERY | TRENDING | FOLLOW_UP
    editorial_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Legacy & UI presentation properties
    section: Mapped[str] = mapped_column(
        String(100), default="TOP STORIES", index=True, nullable=False
    )
    layout_type: Mapped[str] = mapped_column(
        String(30), default="STANDARD", nullable=False
    )
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    personalization_reason: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    display_headline: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    edition: Mapped["NewspaperEdition"] = relationship(
        "NewspaperEdition", back_populates="stories"
    )
    section_rel: Mapped[Optional["NewspaperSection"]] = relationship(
        "NewspaperSection", back_populates="stories"
    )
    story: Mapped[Optional["Story"]] = relationship("Story")
    article: Mapped[Optional["Article"]] = relationship(
        "Article", backref="newspaper_story_placements"
    )


class StoryCluster(Base):
    __tablename__ = "story_clusters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cluster_key: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    articles: Mapped[List["StoryClusterArticle"]] = relationship(
        "StoryClusterArticle", back_populates="cluster", cascade="all, delete-orphan"
    )


class StoryClusterArticle(Base):
    __tablename__ = "story_cluster_articles"

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("story_clusters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    similarity_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    cluster: Mapped["StoryCluster"] = relationship(
        "StoryCluster", back_populates="articles"
    )
    article: Mapped["Article"] = relationship("Article")
