"""evidence_models.py — Phase 19 Advanced User Behavioral Learning Engine Models.

Defines database schemas for:
- Granular behavioral evidence (user_interest_evidence)
- Multi-layer topic behavior preferences (user_topic_behavior_preferences)
- Entity behavior preferences (user_entity_behavior_preferences)
- Short-term story affinity signals (user_story_interest_signals)
- Recurring keyword behavior preferences (user_keyword_behavior_preferences)
"""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import (
    Column,
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
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.topic import Topic
    from app.models.entity import Entity
    from app.models.article import Article
    from app.story_intelligence.models import Story


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserInterestEvidence(Base):
    """
    Granular, immutable behavioral evidence records.
    Captures exact signal types, dwell times, completion ratios, and source provenance.
    """
    __tablename__ = "user_interest_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    signal_type: Mapped[str] = mapped_column(
        String(50), index=True, nullable=False
    )  # OPEN | READ | COMPLETE | SAVE | LIKE | NOT_INTERESTED | SEARCH | CLICK | SKIP | DISCOVERY_CLICK | STORY_OPEN | STORY_FOLLOW_UP
    target_type: Mapped[str] = mapped_column(
        String(30), index=True, nullable=False
    )  # TOPIC | ENTITY | KEYWORD | SOURCE | STORY
    target_id: Mapped[Optional[str]] = mapped_column(
        String(255), index=True, nullable=True
    )
    target_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    strength: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    dwell_time_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completion_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_article_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_story_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_accidental: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    event_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="behavior_evidence")
    article: Mapped[Optional["Article"]] = relationship("Article")
    story: Mapped[Optional["Story"]] = relationship("Story")

    __table_args__ = (
        Index("idx_user_evidence_unprocessed", "user_id", "processed", "created_at"),
        Index("idx_user_evidence_target", "user_id", "target_type", "target_id"),
    )


class UserTopicBehaviorPreference(Base):
    """
    Unified continuous multi-layer behavioral preference model for a (user, topic) pair.
    Combines long-term (45-day half-life), short-term (7-day half-life), and session boosts.
    """
    __tablename__ = "user_topic_behavior_preferences"

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
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # Normalized -1.0 to +1.0
    confidence: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)  # Normalized 0.0 to 1.0
    positive_evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    short_term_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 7-day window
    long_term_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 30-90 day window
    session_boost_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # Decays rapidly
    distinct_story_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    distinct_source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    explicit_override: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # POSITIVE | NEGATIVE | MUTED | None
    last_signal_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="topic_behavior_preferences")
    topic: Mapped["Topic"] = relationship("Topic")

    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_user_topic_behavior"),
        Index("idx_user_topic_behavior_score", "user_id", "score", "confidence"),
    )


class UserEntityBehaviorPreference(Base):
    """
    Behavioral preference model for entities (e.g. OpenAI vs AI Regulation).
    """
    __tablename__ = "user_entity_behavior_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # -1.0 to +1.0
    confidence: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)  # 0.0 to 1.0
    positive_evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    short_term_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    long_term_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    distinct_story_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_signal_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="entity_behavior_preferences")
    entity: Mapped["Entity"] = relationship("Entity")

    __table_args__ = (
        UniqueConstraint("user_id", "entity_id", name="uq_user_entity_behavior"),
        Index("idx_user_entity_behavior_score", "user_id", "score", "confidence"),
    )


class UserStoryInterestSignal(Base):
    """
    Short-term temporary interest affinity in a developing story.
    Expires rapidly upon story resolution.
    """
    __tablename__ = "user_story_interest_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    interaction_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_signal_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="story_interest_signals")
    story: Mapped["Story"] = relationship("Story")

    __table_args__ = (
        UniqueConstraint("user_id", "story_id", name="uq_user_story_signal"),
        Index("idx_user_story_signal_exp", "user_id", "expires_at"),
    )


class UserKeywordBehaviorPreference(Base):
    """
    High-signal recurring keyword affinities.
    """
    __tablename__ = "user_keyword_behavior_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    interaction_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_signal_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="keyword_behavior_preferences")

    __table_args__ = (
        UniqueConstraint("user_id", "keyword", name="uq_user_keyword_behavior"),
    )
