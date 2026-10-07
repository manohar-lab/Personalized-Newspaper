"""evidence_schemas.py — Phase 19 Advanced Behavioral Learning Schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RecordEvidenceRequest(BaseModel):
    signal_type: str = Field(..., description="OPEN, READ, COMPLETE, SAVE, LIKE, NOT_INTERESTED, SEARCH, CLICK, SKIP, DISCOVERY_CLICK, STORY_OPEN, STORY_FOLLOW_UP")
    target_type: str = Field(..., description="TOPIC, ENTITY, KEYWORD, SOURCE, STORY")
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    strength: Optional[float] = 1.0
    dwell_time_seconds: Optional[float] = None
    completion_ratio: Optional[float] = None
    source_article_id: Optional[uuid.UUID] = None
    source_story_id: Optional[uuid.UUID] = None
    event_metadata: Optional[Dict[str, Any]] = None


class TopicInterestItem(BaseModel):
    topic_id: uuid.UUID
    topic_name: str
    topic_slug: str
    score: float = Field(..., description="Effective unified score 0.0 to 1.0")
    raw_behavior_score: float = Field(..., description="Behavior score -1.0 to 1.0")
    confidence: float = Field(..., description="Confidence 0.0 to 1.0")
    tier: str = Field(..., description="STRONG | GROWING | LOW_ENGAGEMENT | NEUTRAL | MUTED")
    short_term_score: float
    long_term_score: float
    positive_evidence_count: int
    negative_evidence_count: int
    distinct_stories_count: int
    distinct_sources_count: int
    explicit_override: Optional[str] = None
    last_signal_at: Optional[datetime] = None
    explanation: str


class EntityInterestItem(BaseModel):
    entity_id: uuid.UUID
    entity_name: str
    entity_type: str
    score: float
    confidence: float
    positive_evidence_count: int
    negative_evidence_count: int
    explanation: str


class KeywordInterestItem(BaseModel):
    keyword: str
    score: float
    confidence: float
    interaction_count: int


class StoryAffinityItem(BaseModel):
    story_id: uuid.UUID
    story_title: str
    score: float
    expires_at: datetime


class UserProfileInterestsResponse(BaseModel):
    user_id: uuid.UUID
    strong_interests: List[TopicInterestItem] = Field(default_factory=list, description="High affinity, high confidence topics")
    growing_interests: List[TopicInterestItem] = Field(default_factory=list, description="Emerging short-term topics with rising confidence")
    low_engagement_topics: List[TopicInterestItem] = Field(default_factory=list, description="Topics with low engagement or skips (respectfully labeled)")
    muted_topics: List[TopicInterestItem] = Field(default_factory=list, description="Explicitly muted topics")
    entity_preferences: List[EntityInterestItem] = Field(default_factory=list)
    keyword_preferences: List[KeywordInterestItem] = Field(default_factory=list)
    active_story_affinities: List[StoryAffinityItem] = Field(default_factory=list)
    recent_trending_topics: List[str] = Field(default_factory=list)
    exploration_factor: float = Field(default=0.15, description="Percentage of recommendation space reserved for discovery")
    entropy_balance: float = Field(default=0.85, description="Distribution health score against interest collapse")
    last_rebuilt_at: Optional[datetime] = None


class TopicOverrideRequest(BaseModel):
    topic_id: uuid.UUID
    override_action: str = Field(..., description="INCREASE | DECREASE | MUTE | UNMUTE | REMOVE_OVERRIDE | SET_POSITIVE | SET_NEGATIVE")
    strength: Optional[float] = 1.0


class ProfileRebuildResponse(BaseModel):
    user_id: uuid.UUID
    status: str = "SUCCESS"
    evidence_events_processed: int
    topics_updated: int
    entities_updated: int
    keywords_updated: int
    duration_ms: float
    rebuilt_at: datetime
