"""schemas.py — Automatic Interest Learning Schemas.

Pydantic schemas for behavior event logging, reading session tracking,
and transparent learned profile inspection.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BehaviorEventCreate(BaseModel):
    """Payload to log a behavioral interaction."""
    article_id: uuid.UUID
    event_type: str = Field(
        ...,
        description="Event type: ARTICLE_IMPRESSION | ARTICLE_OPEN | ARTICLE_READ | ARTICLE_LIKE | ARTICLE_SAVE | ARTICLE_NOT_INTERESTED | ARTICLE_SHARE | ARTICLE_SKIP | ARTICLE_COMPLETE",
    )
    value: float = Field(default=1.0, description="Dwell time or magnitude multiplier")
    event_metadata: Optional[Dict[str, Any]] = None


class BehaviorEventResponse(BaseModel):
    """Recorded behavior event confirmation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    article_id: uuid.UUID
    event_type: str
    value: float
    created_at: datetime


class ReadingStartRequest(BaseModel):
    """Payload to initiate a reading session."""
    article_id: uuid.UUID


class ReadingStartResponse(BaseModel):
    """Confirmed initiated reading session."""
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    article_id: uuid.UUID
    started_at: datetime


class ReadingEndRequest(BaseModel):
    """Payload to conclude an active reading session."""
    session_id: uuid.UUID
    article_id: uuid.UUID
    completion_percentage: Optional[float] = Field(
        default=None, description="Client-estimated scroll / completion percentage [0.0, 100.0]"
    )


class ReadingEndResponse(BaseModel):
    """Completed reading session metrics."""
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    article_id: uuid.UUID
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    completion_percentage: float


class LearnedInterestItem(BaseModel):
    """A single topic, entity, or keyword with its learned score, confidence, and source."""
    name: str
    slug: Optional[str] = None
    score: float
    confidence: float
    source: str = "LEARNED"  # EXPLICIT | LEARNED | HYBRID
    interaction_count: int = 0
    positive_count: int = 0
    negative_count: int = 0


class UserLearningProfileResponse(BaseModel):
    """Comprehensive breakdown of explicit vs learned user affinities."""
    user_id: uuid.UUID
    explicit_interests: List[LearnedInterestItem] = Field(default_factory=list)
    learned_topics: List[LearnedInterestItem] = Field(default_factory=list)
    learned_entities: List[LearnedInterestItem] = Field(default_factory=list)
    learned_keywords: List[LearnedInterestItem] = Field(default_factory=list)
    summary: str = ""
