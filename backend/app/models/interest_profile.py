"""interest_profile.py — Phase 13 Dynamic User Interest Intelligence Models.

Defines persistence for dynamic user interest profiles (explicit, learned, inferred),
topic preferences (positive, negative, neutral), learning events with cursor tracking,
and periodic interest profile snapshots.
"""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import (
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    UUID,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.topic import Topic
    from app.models.article import Article
    from app.models.entity import Entity


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserInterestProfile(Base):
    """Represents a continuous dynamic interest score for a (user, topic, interest_type) triple."""
    __tablename__ = "user_interest_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    interest_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="LEARNED"
    )  # EXPLICIT | LEARNED | INFERRED
    score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_positive_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_negative_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="interest_profiles")
    topic: Mapped["Topic"] = relationship("Topic", backref="user_interest_profiles")

    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", "interest_type", name="uq_user_topic_interest_type"),
        Index("idx_user_interest_type_score", "user_id", "interest_type", "score"),
    )


class UserTopicPreference(Base):
    """Explicit / strong preference marker on a topic (POSITIVE, NEGATIVE, NEUTRAL)."""
    __tablename__ = "user_topic_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    preference: Mapped[str] = mapped_column(
        String(20), nullable=False, default="POSITIVE"
    )  # POSITIVE | NEGATIVE | NEUTRAL
    strength: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="topic_preferences")
    topic: Mapped["Topic"] = relationship("Topic", backref="user_topic_preferences")

    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_user_topic_preference"),
        Index("idx_user_topic_preference", "user_id", "preference"),
    )


class InterestLearningEvent(Base):
    """Logs raw behavioral signals with learning cursor state for batch processing without double counting."""
    __tablename__ = "interest_learning_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    signal_type: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # EXPLICIT_INTEREST | LIKE | SAVE | NOT_INTERESTED | DEEP_READ | NORMAL_READ | SHORT_READ | BOUNCE | REPEAT_READ | SEARCH | ARTICLE_IMPRESSION
    signal_strength: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), default="READER", nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    event_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="learning_events")
    article: Mapped[Optional["Article"]] = relationship("Article", backref="learning_events")

    __table_args__ = (
        Index("idx_unprocessed_learning_events", "user_id", "processed", "created_at"),
    )


class UserInterestSnapshot(Base):
    """Periodic point-in-time snapshot of user's active interest profile."""
    __tablename__ = "user_interest_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    top_topics: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    top_entities: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    interest_embedding_version: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)

    user: Mapped["User"] = relationship("User", backref="interest_snapshots")
