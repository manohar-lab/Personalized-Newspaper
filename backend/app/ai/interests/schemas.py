"""schemas.py — Pydantic Schemas for Dynamic User Interest Intelligence.

Defines schemas for dynamic interest profiles, preference management, explanations,
and learning resets.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DynamicInterestItem(BaseModel):
    topic_id: uuid.UUID
    name: str
    slug: str
    score: float
    confidence: float
    interest_type: str = "LEARNED"  # EXPLICIT | LEARNED | INFERRED
    state: str = "STABLE"  # STRONG | EMERGING | STABLE | DECLINING | DORMANT
    evidence_count: int = 1
    positive_count: int = 0
    negative_count: int = 0
    last_positive_at: Optional[datetime] = None
    parent_topic_name: Optional[str] = None


class TopicPreferenceItem(BaseModel):
    topic_id: uuid.UUID
    name: str
    slug: str
    preference: str  # POSITIVE | NEGATIVE | NEUTRAL
    strength: float = 1.0
    confidence: float = 1.0


class EntityAffinityItem(BaseModel):
    entity_id: uuid.UUID
    name: str
    score: float
    confidence: float
    evidence_count: int = 1


class DynamicProfileResponse(BaseModel):
    user_id: uuid.UUID
    explicit_interests: List[DynamicInterestItem] = Field(default_factory=list)
    strong_interests: List[DynamicInterestItem] = Field(default_factory=list)
    emerging_interests: List[DynamicInterestItem] = Field(default_factory=list)
    stable_interests: List[DynamicInterestItem] = Field(default_factory=list)
    declining_interests: List[DynamicInterestItem] = Field(default_factory=list)
    dormant_interests: List[DynamicInterestItem] = Field(default_factory=list)
    avoided_topics: List[TopicPreferenceItem] = Field(default_factory=list)
    top_entities: List[EntityAffinityItem] = Field(default_factory=list)
    summary: str


class UpdateTopicPreferenceRequest(BaseModel):
    topic_id: uuid.UUID
    preference: str = "NEGATIVE"  # POSITIVE | NEGATIVE | NEUTRAL
    strength: Optional[float] = 1.0


class ResetLearnedProfileResponse(BaseModel):
    status: str = "success"
    message: str
    explicit_interests_preserved: int


class RelevanceExplanationResponse(BaseModel):
    article_id: uuid.UUID
    article_title: str
    explanation: str
    primary_factors: List[str] = Field(default_factory=list)
    match_score: float
