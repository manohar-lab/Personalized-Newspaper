import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import Table, Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, UUID, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.topic import Topic
    from app.models.action import UserArticleAction
    from app.models.source import NewsSource
    from app.models.feed import NewsFeed
    from app.models.entity import Entity
    from app.models.analysis import ArticleAnalysis, ArticleKeyword

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# Junction table for Article <-> Topic (Many-to-Many with confidence)
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
    Column(
        "confidence",
        Float,
        default=1.0,
        nullable=False,
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
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feed_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_feeds.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(
        String(1024), index=True, nullable=True
    )
    ingestion_method: Mapped[str] = mapped_column(
        String(20), default="MANUAL", index=True, nullable=False
    )  # RSS | SCRAPER | API | MANUAL
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
    # Phase 5: Extraction & Scraping tracking
    scrape_status: Mapped[Optional[str]] = mapped_column(
        String(30), index=True, nullable=True
    )  # PENDING | SUCCESS | FAILED | ROBOTS_BLOCKED | VALIDATION_FAILED | SKIPPED
    scraped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scrape_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    extraction_status: Mapped[Optional[str]] = mapped_column(
        String(30), index=True, default="NOT_ATTEMPTED", nullable=True
    )  # NOT_ATTEMPTED | PENDING | SUCCESS | PARTIAL | FAILED | ROBOTS_BLOCKED | PAYWALL | ACCESS_DENIED | UNSUPPORTED
    extracted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extraction_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )  # TRAFILATURA | JSON_LD | OPENGRAPH | FALLBACK

    # Relationships
    topics: Mapped[List["Topic"]] = relationship(
        "Topic", secondary=article_topics, backref="articles"
    )
    actions: Mapped[List["UserArticleAction"]] = relationship(
        "UserArticleAction", back_populates="article", cascade="all, delete-orphan"
    )
    source: Mapped[Optional["NewsSource"]] = relationship(
        "NewsSource", back_populates="articles"
    )
    feed: Mapped[Optional["NewsFeed"]] = relationship(
        "NewsFeed", back_populates="articles"
    )
    analysis: Mapped[Optional["ArticleAnalysis"]] = relationship(
        "ArticleAnalysis", back_populates="article", uselist=False, cascade="all, delete-orphan"
    )
    keywords: Mapped[List["ArticleKeyword"]] = relationship(
        "ArticleKeyword", back_populates="article", cascade="all, delete-orphan"
    )
    entities: Mapped[List["Entity"]] = relationship(
        "Entity",
        secondary="article_entities",
        backref="articles",
    )

    @property
    def primary_category(self) -> Optional[str]:
        return self.analysis.primary_category if self.analysis else None

    @property
    def article_type(self) -> Optional[str]:
        return self.analysis.article_type if self.analysis else None

    @property
    def summary(self) -> Optional[str]:
        return self.analysis.summary if self.analysis else None

    @property
    def importance_score(self) -> Optional[float]:
        return self.analysis.importance_score if self.analysis else None
