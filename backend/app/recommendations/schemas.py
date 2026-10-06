"""schemas.py — Phase 14 Recommendation Engine Pydantic Schemas."""
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    article_id: uuid.UUID
    title: str
    summary: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[datetime] = None
    image: Optional[str] = None
    reading_time: Optional[int] = None
    recommendation_score_hidden: float = Field(default=0.0, description="Internal score not shown in main UI")
    reason_type: str = Field(..., description="e.g. STRONG_INTEREST, RELATED_TO_READING, EMERGING_INTEREST, TRENDING_FOR_YOU, DISCOVERY, SIMILAR_ARTICLE")
    reason_text: str = Field(..., description="Human friendly explanation")
    section: Optional[str] = Field(default="Recommended for you", description="UI section grouping: Recommended for you, Trending in your interests, Discover something new")
    is_new: bool = Field(default=True)
    is_read: bool = Field(default=False)

    model_config = {"from_attributes": True}


class RecommendationFeedResponse(BaseModel):
    total: int
    page: int = 1
    limit: int = 20
    context: str = "DISCOVER"
    recommendations: List[RecommendationItem] = []
    recommended_for_you: List[RecommendationItem] = []
    trending_in_your_interests: List[RecommendationItem] = []
    discover_something_new: List[RecommendationItem] = []


class TrendingForYouResponse(BaseModel):
    total: int
    recommendations: List[RecommendationItem] = []


class MoreLikeThisResponse(BaseModel):
    article_id: uuid.UUID
    recommendations: List[RecommendationItem] = []


class RecommendationInteractionRequest(BaseModel):
    article_id: uuid.UUID
    interaction_type: str = Field(..., description="IMPRESSION | CLICK")
    context: Optional[str] = "DISCOVER"
