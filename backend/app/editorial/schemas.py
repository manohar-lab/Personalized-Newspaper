"""schemas.py — Phase 17 Editorial Newspaper Engine Data Schemas & Contracts."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class EditorialRole(str, Enum):
    LEAD = "LEAD"
    TOP_STORY = "TOP_STORY"
    STANDARD = "STANDARD"
    BRIEF = "BRIEF"
    DISCOVERY = "DISCOVERY"
    TRENDING = "TRENDING"
    FOLLOW_UP = "FOLLOW_UP"


class SectionType(str, Enum):
    LEAD = "LEAD"
    TOP_STORIES = "TOP_STORIES"
    TECHNOLOGY = "TECHNOLOGY"
    BUSINESS = "BUSINESS"
    SCIENCE = "SCIENCE"
    WORLD = "WORLD"
    INDIA = "INDIA"
    SPORTS = "SPORTS"
    ENTERTAINMENT = "ENTERTAINMENT"
    DISCOVER = "DISCOVER"
    FOR_YOU = "FOR_YOU"


class EditionStatus(str, Enum):
    GENERATING = "GENERATING"
    READY = "READY"
    STALE = "STALE"
    FAILED = "FAILED"


class EditorialCandidate(BaseModel):
    """Rich candidate representation passed through the editorial pipeline."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    story_id: Optional[uuid.UUID] = None
    article_id: uuid.UUID
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    top_image_url: Optional[str] = None
    source_name: Optional[str] = "Independent Source"
    source_id: Optional[uuid.UUID] = None
    published_at: Optional[datetime] = None
    reading_time_minutes: int = 3
    primary_category: Optional[str] = "GENERAL"
    topics: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    embedding: Optional[List[float]] = None

    # Quality & Story Intelligence
    importance_score: float = 0.5
    quality_score: float = 0.5
    activity_score: float = 0.5
    source_count: int = 1
    independent_source_count: int = 1
    is_developing: bool = False
    is_breaking: bool = False
    is_syndicated: bool = False

    # Personal Relevance & User State
    personal_relevance_score: float = 0.5
    user_affinity_score: float = 0.0
    recency_score: float = 0.5
    novelty_score: float = 0.5
    public_importance_bonus: float = 0.0
    recently_seen_penalty: float = 0.0
    duplicate_coverage_penalty: float = 0.0

    # Reading History State
    is_read: bool = False
    user_read_percentage: float = 0.0
    has_meaningful_update: bool = False

    # Pipeline output parameters
    editorial_score: float = 0.5
    editorial_role: str = EditorialRole.STANDARD.value
    assigned_section: str = SectionType.TOP_STORIES.value
    reason: Optional[str] = None
    story_slug: Optional[str] = None
    story_article_count: int = 1
    story_source_count: int = 1
    is_discovery_candidate: bool = False


class EditorialWeights(BaseModel):
    """Configurable weights for the centralized editorial scoring formula."""
    weight_personal_relevance: float = 0.35
    weight_global_importance: float = 0.20
    weight_recency: float = 0.15
    weight_story_activity: float = 0.10
    weight_source_quality: float = 0.10
    weight_novelty: float = 0.05
    weight_user_affinity: float = 0.05
    public_importance_multiplier: float = 0.15
    read_penalty_factor: float = 0.40
    duplicate_penalty_factor: float = 0.25
    section_diversity_weight: float = 0.10
    max_stories_per_section: int = 6


class EditorialDecision(BaseModel):
    """Record of why a story was placed or excluded for admin debug inspection."""
    item_id: str
    title: str
    editorial_score: float
    role: str
    section: str
    decision: str  # SELECTED | EXCLUDED
    reason: str
    factors: Dict[str, float] = Field(default_factory=dict)


class EditorialDebugResponse(BaseModel):
    """Admin debug endpoint response payload."""
    user_id: uuid.UUID
    edition_date: str
    version: int
    candidate_count: int
    selected_count: int
    excluded_count: int
    lead_selection: Optional[Dict[str, Any]] = None
    section_assignments: Dict[str, int] = Field(default_factory=dict)
    diversity_decisions: Dict[str, Any] = Field(default_factory=dict)
    selected_stories: List[EditorialDecision] = Field(default_factory=list)
    excluded_stories: List[EditorialDecision] = Field(default_factory=list)


class EditionVersionSummary(BaseModel):
    """Summary of a specific edition version."""
    id: uuid.UUID
    version: int
    edition_date: str
    status: str
    generated_at: datetime
    total_stories: int
    lead_title: Optional[str] = None
    editorial_summary: Optional[str] = None


class EditionStatusResponse(BaseModel):
    """Status check for today's or a specific edition."""
    edition_date: str
    version: int
    status: str
    generated_at: Optional[datetime] = None
    is_stale: bool = False
    stale_reasons: List[str] = Field(default_factory=list)
