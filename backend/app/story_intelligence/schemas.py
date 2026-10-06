"""schemas.py — Phase 16 Multi-Source Story Intelligence Schemas."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class StoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEVELOPING = "DEVELOPING"
    STABLE = "STABLE"
    RESOLVED = "RESOLVED"
    ARCHIVED = "ARCHIVED"


class StoryRelationshipType(str, Enum):
    PRIMARY = "PRIMARY"
    UPDATE = "UPDATE"
    ANALYSIS = "ANALYSIS"
    REACTION = "REACTION"
    BACKGROUND = "BACKGROUND"
    RELATED = "RELATED"


class StoryArticleItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    article_id: uuid.UUID
    title: str
    summary: Optional[str] = None
    url: Optional[str] = None
    source_name: Optional[str] = "Independent Source"
    published_at: Optional[datetime] = None
    relationship_type: str = "PRIMARY"
    similarity_score: float = 1.0
    top_image_url: Optional[str] = None
    reading_time_minutes: int = 3
    is_syndicated: bool = False
    potential_conflict: bool = False


class StoryTimelineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    article_id: uuid.UUID
    title: str
    source_name: Optional[str] = "Independent Source"
    published_at: datetime
    relationship_type: str
    url: Optional[str] = None
    snippet: Optional[str] = None


class StoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    summary: Optional[str] = None
    status: str = "ACTIVE"
    importance_score: float = 0.5
    quality_score: float = 0.5
    activity_score: float = 0.5
    article_count: int = 1
    source_count: int = 1
    independent_source_count: int = 1
    first_published_at: datetime
    last_updated_at: datetime
    primary_topic_name: Optional[str] = None
    primary_article_id: Optional[uuid.UUID] = None
    latest_article_id: Optional[uuid.UUID] = None
    primary_article: Optional[Dict[str, Any]] = None
    latest_article: Optional[Dict[str, Any]] = None
    has_conflicts: bool = False
    conflict_note: Optional[str] = None
    personal_score: Optional[float] = None


class StoryDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    summary: Optional[str] = None
    status: str = "ACTIVE"
    importance_score: float = 0.5
    quality_score: float = 0.5
    activity_score: float = 0.5
    article_count: int = 1
    source_count: int = 1
    independent_source_count: int = 1
    first_published_at: datetime
    last_updated_at: datetime
    primary_topic_id: Optional[uuid.UUID] = None
    primary_topic_name: Optional[str] = None
    primary_article: Optional[StoryArticleItem] = None
    latest_article: Optional[StoryArticleItem] = None
    articles: List[StoryArticleItem] = Field(default_factory=list)
    timeline: List[StoryTimelineItem] = Field(default_factory=list)
    has_conflicts: bool = False
    conflict_note: Optional[str] = None
    sources: List[str] = Field(default_factory=list)


class StoryCoverageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    story_id: uuid.UUID
    story_title: str
    story_slug: str
    total_articles: int
    total_sources: int
    independent_source_count: int
    articles_by_relationship: Dict[str, List[StoryArticleItem]] = Field(
        default_factory=dict
    )
    sources: List[str] = Field(default_factory=list)
    has_conflicts: bool = False
    conflict_details: Optional[List[Dict[str, Any]]] = None


class StoryFeedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: List[StoryItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 20
    has_next: bool = False


class StorySearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query: str
    total: int
    results: List[StoryItem] = Field(default_factory=list)


class StoryMergeRequest(BaseModel):
    source_story_id: uuid.UUID
    target_story_id: uuid.UUID
    reason: Optional[str] = "Identified duplicate evolving coverage"
