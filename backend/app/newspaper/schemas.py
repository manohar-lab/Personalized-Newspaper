"""schemas.py — Phase 9 Newspaper Edition & Story Schemas."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.article import TopicSummary


class StoryLayoutType(str, Enum):
    LEAD = "LEAD"
    FEATURE = "FEATURE"
    STANDARD = "STANDARD"
    COMPACT = "COMPACT"


class ControlledSection(str, Enum):
    TOP_STORIES = "TOP STORIES"
    TECHNOLOGY = "TECHNOLOGY"
    SCIENCE = "SCIENCE"
    BUSINESS = "BUSINESS"
    WORLD = "WORLD"
    HEALTH = "HEALTH"
    SPORTS = "SPORTS"
    ENTERTAINMENT = "ENTERTAINMENT"
    OTHER = "OTHER"


class NewspaperStoryResponse(BaseModel):
    """Article presentation item within an edition with editorial layout parameters."""
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    id: uuid.UUID
    article_id: uuid.UUID
    title: str
    original_headline: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    top_image_url: Optional[str] = None
    author: Optional[str] = None
    source_name: Optional[str] = "Independent Source"
    published_at: Optional[datetime] = None
    reading_time_minutes: int = 3
    is_full_text_available: bool = True
    primary_category: Optional[str] = None
    topics: List[str] = Field(default_factory=list)

    # Editorial layout fields
    section: str = "TOP STORIES"
    position: int = 0
    layout_type: str = "STANDARD"  # LEAD | FEATURE | STANDARD | COMPACT
    editorial_score: float = 0.5
    is_lead: bool = False
    personalization_reason: Optional[str] = None
    display_headline: Optional[str] = None
    status: str = "PUBLISHED"

    # User action state
    is_saved: bool = False
    is_liked: bool = False
    is_read: bool = False
    is_not_interested: bool = False
    relevance_score: Optional[float] = None

    # Story Intelligence Integration
    story_id: Optional[uuid.UUID] = None
    story_slug: Optional[str] = None
    story_article_count: Optional[int] = 1
    story_source_count: Optional[int] = 1



class NewspaperSectionResponse(BaseModel):
    """A populated editorial section containing ranked stories."""
    model_config = ConfigDict(from_attributes=True)

    name: str
    display_name: str
    story_count: int = 0
    stories: List[NewspaperStoryResponse] = Field(default_factory=list)
    articles: List[NewspaperStoryResponse] = Field(default_factory=list)
    topic: Optional[Dict[str, Any]] = None


class NewspaperEditionResponse(BaseModel):
    """Complete daily newspaper edition snapshot."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    edition_date: str
    title: str = "YOUR DAILY"
    subtitle: Optional[str] = None
    status: str = "READY"
    generated_at: datetime
    curation_summary: Optional[str] = None
    has_interests: bool = True
    lead_story: Optional[NewspaperStoryResponse] = None
    featured_article: Optional[Any] = None
    edition: Optional[Dict[str, Any]] = None
    user: Optional[Dict[str, Any]] = None
    sections: List[NewspaperSectionResponse] = Field(default_factory=list)
    total_stories: int = 0


class GenerateEditionRequest(BaseModel):
    """Payload to trigger newspaper generation."""
    edition_date: Optional[str] = Field(
        default=None, description="Target date in YYYY-MM-DD format (defaults to current UTC date)"
    )
    force_refresh: bool = Field(
        default=False, description="Whether to overwrite existing edition for the date"
    )
