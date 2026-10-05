import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, HttpUrl, Field


class TopicBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class SourceBase(BaseModel):
    name: str
    slug: str
    website_url: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool = True


class SourceCreate(SourceBase):
    pass


class SourceResponse(SourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    feeds_count: Optional[int] = 0


class FeedBase(BaseModel):
    source_id: uuid.UUID
    name: str
    feed_url: str
    feed_type: str = "RSS"  # RSS | ATOM
    language: str = "en"
    is_active: bool = True
    default_topic_id: Optional[uuid.UUID] = None


class FeedCreate(FeedBase):
    pass


class FeedResponse(FeedBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_name: Optional[str] = None
    default_topic_name: Optional[str] = None
    last_fetched_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FeedTestSampleArticle(BaseModel):
    title: str
    description: Optional[str] = None
    url: str
    canonical_url: Optional[str] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    published_at: Optional[datetime] = None
    content_hash: Optional[str] = None


class FeedTestResponse(BaseModel):
    feed_title: Optional[str] = None
    feed_description: Optional[str] = None
    feed_url: str
    feed_type: str
    entries_count: int
    is_valid: bool
    sample_entries: List[FeedTestSampleArticle] = []
    error: Optional[str] = None


class IngestionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feed_id: uuid.UUID
    feed_name: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    articles_fetched: int
    articles_created: int
    duplicates_found: int
    errors_count: int
    error_message: Optional[str] = None


class IngestionSummary(BaseModel):
    feed: str
    feed_id: Optional[uuid.UUID] = None
    fetched: int
    new_articles: int
    duplicates: int
    failed: int
    status: str
    error_message: Optional[str] = None


class IngestionBatchResponse(BaseModel):
    total_feeds: int
    successful_feeds: int
    failed_feeds: int
    total_articles_fetched: int
    total_articles_created: int
    total_duplicates_found: int
    results: List[IngestionSummary]
