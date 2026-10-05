"""schemas.py — Phase 11 Intelligent Personalized Search Engine Schemas."""
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
    date_preset: Optional[str] = Field(default=None, description="Preset: today | yesterday | last_7_days | last_30_days")
    article_type: Optional[str] = Field(default=None, description="Filter by article type (e.g. NEWS, ANALYSIS, OPINION)")
    language: Optional[str] = Field(default=None, description="Filter by language (e.g. en)")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=50, description="Page size (max 50)")


class SearchResultItem(BaseModel):
    """A ranked search result item."""
    model_config = ConfigDict(from_attributes=True)

    article_id: uuid.UUID
    title: str
    summary: Optional[str] = None
    source_name: Optional[str] = "Independent Source"
    published_at: Optional[datetime] = None
    primary_category: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    top_image_url: Optional[str] = None
    reading_time_minutes: int = 3
    is_full_text_available: bool = True

    # Scoring details
    full_text_score: float = 0.0
    semantic_score: float = 0.0
    search_score: float = 0.0
    personal_relevance_score: Optional[float] = None
    final_score: float = 0.0
    match_explanation: Optional[str] = None


class ParsedQueryInfo(BaseModel):
    """Information extracted by QueryParser."""
    raw_query: str
    clean_keywords: str
    detected_topics: List[str] = Field(default_factory=list)
    detected_entities: List[str] = Field(default_factory=list)
    detected_sources: List[str] = Field(default_factory=list)
    date_range_detected: Optional[str] = None


class SearchResponse(BaseModel):
    """Complete paginated search response."""
    model_config = ConfigDict(from_attributes=True)

    query: str
    total_results: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 1
    results: List[SearchResultItem] = Field(default_factory=list)
    parsed_query: Optional[ParsedQueryInfo] = None
    execution_time_ms: float = 0.0


class SearchSuggestionItem(BaseModel):
    """Single autocomplete/search suggestion."""
    text: str
    type: str  # TOPIC | ENTITY | KEYWORD | RECENT
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
    filters: Optional[str] = None
    result_count: int = 0
    created_at: datetime


class SearchHistoryResponse(BaseModel):
    """List of user search history."""
    history: List[SearchHistoryItem] = Field(default_factory=list)
