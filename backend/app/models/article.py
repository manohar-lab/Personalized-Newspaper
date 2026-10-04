import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import Table, Column, String, Text, Integer, Boolean, DateTime, ForeignKey, UUID, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.topic import Topic
    from app.models.action import UserArticleAction

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# Junction table for Article <-> Topic (Many-to-Many)
article_topics = Table(
    "article_topics",
    Base.metadata,
    Column(
        "article_id",
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column(
        "topic_id",
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(500), unique=True, index=True, nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    reading_time_minutes: Mapped[int] = mapped_column(
        Integer, default=3, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="PUBLISHED", index=True, nullable=False
    )  # DRAFT | PUBLISHED | ARCHIVED
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, nullable=True
    )
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    is_full_text_available: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Relationships
    topics: Mapped[List["Topic"]] = relationship(
        "Topic", secondary=article_topics, backref="articles"
    )
    actions: Mapped[List["UserArticleAction"]] = relationship(
        "UserArticleAction", back_populates="article", cascade="all, delete-orphan"
    )
