"""schemas.py — Phase 24 Intelligent Personalized Search Engine Schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SearchFilterParams(BaseModel):
    """Optional search filter parameters."""
    q: str = Field(default="", description="Search query text")
    topic: Optional[str] = Field(default=None, description="Filter by topic slug or name")
    category: Optional[str] = Field(default=None, description="Filter by primary category")
    source: Optional[str] = Field(default=None, description="Filter by source name (single or comma-separated)")
    date_from: Optional[datetime] = Field(default=None, description="Filter articles published on or after")
    date_to: Optional[datetime] = Field(default=None, description="Filter articles published on or before")
    date_preset: Optional[str] = Field(default=None, description="Preset: today | yesterday | last_24_hours | last_7_days | last_30_days")
    article_type: Optional[str] = Field(default=None, description="Filter by article type (e.g. NEWS, ANALYSIS, OPINION)")
    language: Optional[str] = Field(default=None, description="Filter by language (e.g. en)")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=50, description="Page size (max 50)")
    sort_by: Optional[str] = Field(default="relevance", description="relevance | newest | importance")
    read_status: Optional[str] = Field(default=None, description="all | read | unread")
    saved_status: Optional[str] = Field(default=None, description="all | saved | unsaved")
    result_type: Optional[str] = Field(default="ALL", description="ALL | STORIES | ARTICLES | TOPICS | ENTITIES")
    deduplicate: bool = Field(default=True, description="Whether to deduplicate articles covering same stories or identical headlines")


class SearchResultItem(BaseModel):
    """A ranked article search result item."""
    model_config = ConfigDict(from_attributes=True)

    article_id: uuid.UUID
    title: str
    summary: Optional[str] = None
    source_name: Optional[str] = "Independent Source"
    source_url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    primary_category: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    top_image_url: Optional[str] = None
    reading_time_minutes: int = 3
    is_full_text_available: bool = True
    is_paywalled: bool = False
    read_status: Optional[str] = None
    saved_status: Optional[str] = None

    # Scoring details (preserved for backwards-compatibility and ranking evaluation)
    full_text_score: float = 0.0
    semantic_score: float = 0.0
    search_score: float = 0.0
    personal_relevance_score: Optional[float] = None
    final_score: float = 0.0
    match_explanation: Optional[str] = None


class SearchStoryItem(BaseModel):
    """A matching story result item."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    summary: Optional[str] = None
    article_count: int = 1
    source_count: int = 1
    status: str = "ACTIVE"
    importance_score: float = 0.5
    last_updated_at: Optional[datetime] = None
    first_published_at: Optional[datetime] = None
    primary_topic_name: Optional[str] = None
    read_story_link: str


class SearchTopicItem(BaseModel):
    """A matching topic result item."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    is_followed: bool = False
    article_count: int = 0


class SearchEntityItem(BaseModel):
    """A matching entity result item."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    entity_type: str = "OTHER"
    is_followed: bool = False
    is_muted: bool = False
    story_count: int = 0
    article_count: int = 0


class ParsedQueryInfo(BaseModel):
    """Information extracted by QueryParser."""
    raw_query: str
    clean_keywords: str
    detected_topics: List[str] = Field(default_factory=list)
    detected_entities: List[str] = Field(default_factory=list)
    detected_sources: List[str] = Field(default_factory=list)
    date_range_detected: Optional[str] = None


class SearchResponse(BaseModel):
    """Complete paginated hybrid search response across stories, articles, topics, and entities."""
    model_config = ConfigDict(from_attributes=True)

    query: str
    total_results: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 1
    results: List[SearchResultItem] = Field(default_factory=list)  # Backwards compatibility
    articles: List[SearchResultItem] = Field(default_factory=list) # Phase 24 specification
    stories: List[SearchStoryItem] = Field(default_factory=list)
    topics: List[SearchTopicItem] = Field(default_factory=list)
    entities: List[SearchEntityItem] = Field(default_factory=list)
    total_counts: Dict[str, int] = Field(default_factory=dict)
    applied_filters: Dict[str, Any] = Field(default_factory=dict)
    query_metadata: Dict[str, Any] = Field(default_factory=dict)
    parsed_query: Optional[ParsedQueryInfo] = None
    execution_time_ms: float = 0.0


class SearchSuggestionItem(BaseModel):
    """Single autocomplete/search suggestion."""
    text: str
    type: str  # TOPIC | ENTITY | STORY | RECENT | KEYWORD
    subtitle: Optional[str] = None


class SearchSuggestionsResponse(BaseModel):
    """Autocomplete search suggestions."""
    query: str
    suggestions: List[SearchSuggestionItem] = Field(default_factory=list)


class SearchHistoryItem(BaseModel):
    """Search history record."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query: str
    normalized_query: Optional[str] = None
    filters: Optional[str] = None
    result_count: int = 0
    created_at: datetime
    searched_at: Optional[datetime] = None


class SearchHistoryResponse(BaseModel):
    """List of user search history."""
    history: List[SearchHistoryItem] = Field(default_factory=list)


class SearchRecentResponse(BaseModel):
    """List of user recent searches."""
    recent: List[SearchHistoryItem] = Field(default_factory=list)


class SearchFiltersMetaResponse(BaseModel):
    """Metadata of available search filters for frontend UI."""
    categories: List[str] = Field(default_factory=list)
    date_presets: List[Dict[str, str]] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    sort_options: List[Dict[str, str]] = Field(default_factory=list)
    result_types: List[Dict[str, str]] = Field(default_factory=list)
