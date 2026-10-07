"""models.py — Phase 18 Personal News Briefing & Session Models."""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from sqlalchemy import (
    Boolean,
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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BriefingStatus(str, Enum):
    GENERATING = "GENERATING"
    READY = "READY"
    STALE = "STALE"
    FAILED = "FAILED"


class BriefingType(str, Enum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    FOLLOW_UP = "FOLLOW_UP"
    IMPORTANT = "IMPORTANT"
    FOR_YOU = "FOR_YOU"
    DISCOVERY = "DISCOVERY"


class Daypart(str, Enum):
    MORNING = "MORNING"
    MIDDAY = "MIDDAY"
    EVENING = "EVENING"
    NIGHT = "NIGHT"


class NewsBriefing(Base):
    """
    Personalized daily news briefing for a user.
    Represents "What has changed since your last visit?"
    """
    __tablename__ = "news_briefings"
    __table_args__ = (
        UniqueConstraint("user_id", "briefing_date", "version", name="uq_user_briefing_date_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("newspaper_editions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    briefing_date: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # YYYY-MM-DD
    daypart: Mapped[str] = mapped_column(
        String(20), default=Daypart.MORNING.value, nullable=False
    )  # MORNING | MIDDAY | EVENING | NIGHT
    title: Mapped[str] = mapped_column(
        String(255), default="YOUR DAILY BRIEFING", nullable=False
    )
    intro: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=BriefingStatus.GENERATING.value, nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    is_caught_up: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
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

    # Relationships
    user = relationship("User", backref="news_briefings")
    edition = relationship("NewspaperEdition", backref="briefings")
    items: Mapped[List["NewsBriefingItem"]] = relationship(
        "NewsBriefingItem",
        back_populates="briefing",
        cascade="all, delete-orphan",
        order_by="NewsBriefingItem.position",
        lazy="selectin",
    )


class NewsBriefingItem(Base):
    """
    Individual curated item within a personal news briefing.
    """
    __tablename__ = "news_briefing_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    briefing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_briefings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    story_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    position: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    briefing_type: Mapped[str] = mapped_column(
        String(30), default=BriefingType.NEW.value, nullable=False
    )  # NEW | UPDATED | FOLLOW_UP | IMPORTANT | FOR_YOU | DISCOVERY
    headline: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    importance: Mapped[float] = mapped_column(
        Float, default=0.5, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    briefing: Mapped["NewsBriefing"] = relationship("NewsBriefing", back_populates="items")
    story = relationship("Story", backref="briefing_items", lazy="selectin")
    article = relationship("Article", backref="briefing_items", lazy="selectin")


class NewsSession(Base):
    """
    Tracks meaningful news consumption sessions for a user to determine
    "What has changed since you last checked the news?"
    """
    __tablename__ = "news_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    stories_viewed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    articles_opened: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    meaningful_activity: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    user = relationship("User", backref="news_sessions")
