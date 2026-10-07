"""personalization.py — Phase 23 Personalization Control Center Schemas."""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class PersonalizationSettingsResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    discovery_level: str = "BALANCED"  # FOCUSED | BALANCED | EXPLORATORY
    personalization_strength: str = "BALANCED"  # LOW | BALANCED | HIGH
    diversity_level: str = "BALANCED"  # FOCUSED | BALANCED | DIVERSE
    learning_enabled: bool = True
    section_preferences: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PersonalizationSettingsUpdate(BaseModel):
    discovery_level: Optional[str] = Field(None, pattern="^(FOCUSED|BALANCED|EXPLORATORY)$")
    personalization_strength: Optional[str] = Field(None, pattern="^(LOW|BALANCED|HIGH)$")
    diversity_level: Optional[str] = Field(None, pattern="^(FOCUSED|BALANCED|DIVERSE)$")
    learning_enabled: Optional[bool] = None
    section_preferences: Optional[Dict[str, str]] = None


class ExplicitInterestItem(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    topic_name: str
    topic_slug: str
    preference_type: str = "POSITIVE"  # POSITIVE | NEGATIVE
    interest_score: float = 0.8
    source: str = "USER_ACTION"
    created_at: datetime


class InferredInterestItem(BaseModel):
    topic_id: uuid.UUID
    topic_name: str
    topic_slug: str
    tier: str  # "Strong interest" | "Growing interest" | "Moderate interest" | "Low recent interest"
    why_reason: str
    reads_count: int = 0
    saves_count: int = 0
    searches_count: int = 0
    completion_avg: float = 0.0


class TopicControlItem(BaseModel):
    topic_id: uuid.UUID
    topic_name: str
    topic_slug: str
    parent_id: Optional[uuid.UUID] = None
    parent_name: Optional[str] = None
    status: str = "NEUTRAL"  # FOLLOWING | MUTED | SUGGESTED | NEUTRAL
    strength_label: str = "Moderate"
    why_reason: Optional[str] = None


class EntityControlItem(BaseModel):
    entity_id: uuid.UUID
    name: str
    entity_type: Optional[str] = "CONCEPT"
    status: str = "NEUTRAL"  # FOLLOWING | MUTED | LESS | NEUTRAL
    interaction_count: int = 0
    why_reason: str


class SourceControlItem(BaseModel):
    source_id: uuid.UUID
    name: str
    domain: Optional[str] = None
    status: str = "NEUTRAL"  # PREFERRED | MUTED | REDUCED | NEUTRAL
    read_count: int = 0
    affinity_label: str = "Regular"


class TemporaryInterestItem(BaseModel):
    story_id: uuid.UUID
    title: str
    topic_name: Optional[str] = None
    interaction_count: int = 1
    expires_at: Optional[datetime] = None


class WhyThisStoryResponse(BaseModel):
    article_id: uuid.UUID
    title: str
    primary_reason: str
    reasons: List[str]  # 1 to 3 human bullet points
    topic_id: Optional[uuid.UUID] = None
    topic_name: Optional[str] = None
    source_name: Optional[str] = None
    is_breaking_override: bool = False


class PersonalizationProfileResponse(BaseModel):
    explicit_interests: List[ExplicitInterestItem]
    inferred_interests: List[InferredInterestItem]
    following_topics: List[TopicControlItem]
    muted_topics: List[TopicControlItem]
    suggested_topics: List[TopicControlItem]
    entities: List[EntityControlItem]
    sources: List[SourceControlItem]
    temporary_interests: List[TemporaryInterestItem]
    settings: PersonalizationSettingsResponse
    learning_stats: Dict[str, int]
    privacy_transparency: Dict[str, Any]
