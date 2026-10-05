"""schemas.py — Phase 8 Personal Relevance Scoring Schemas.

Data structures for score breakdowns, user profile contexts, and ranking results.
"""
import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RelevanceScoreBreakdown(BaseModel):
    """Transparent score breakdown for development debugging and auditing."""
    final_score: float = Field(..., description="Overall clamped relevance score [0.0, 1.0]")
    topic_score: float = Field(default=0.0, description="Topic alignment score [0.0, 1.0]")
    semantic_score: float = Field(default=0.0, description="Embedding cosine similarity score [0.0, 1.0]")
    entity_score: float = Field(default=0.0, description="Entity relevance score [0.0, 1.0]")
    keyword_score: float = Field(default=0.0, description="Keyword overlap score [0.0, 1.0]")
    importance_score: float = Field(default=0.0, description="Global article importance score [0.0, 1.0]")
    recency_score: float = Field(default=0.0, description="Time decay recency score [0.0, 1.0]")
    negative_penalty: float = Field(default=0.0, description="Penalty deducted for negative topic matches")
    source_score: Optional[float] = Field(default=0.0, description="Optional source preference adjustment")


class UserInterestProfile(BaseModel):
    """Normalized in-memory snapshot of a user's explicit and semantic interests."""
    user_id: uuid.UUID
    positive_interests: Dict[str, float] = Field(default_factory=dict)  # topic_slug -> interest_score
    negative_interests: Dict[str, float] = Field(default_factory=dict)  # topic_slug -> interest_score
    topic_names_map: Dict[str, str] = Field(default_factory=dict)       # topic_slug -> topic_name
    topic_ids_map: Dict[str, uuid.UUID] = Field(default_factory=dict)   # topic_slug -> topic_id
    learned_entities: Dict[str, float] = Field(default_factory=dict)     # entity_name/slug -> score
    learned_keywords: Dict[str, float] = Field(default_factory=dict)     # keyword -> score
    embedding: Optional[List[float]] = None
    has_interests: bool = False


class ScoredArticle(BaseModel):
    """Container pairing an article with its evaluated personal relevance."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    article_id: uuid.UUID
    relevance_score: float
    breakdown: RelevanceScoreBreakdown
