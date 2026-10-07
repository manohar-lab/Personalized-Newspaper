"""schemas.py — Phase 18 Personal News Briefing Pydantic Schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.briefings.models import BriefingStatus, BriefingType, Daypart


class BriefingItemResponse(BaseModel):
    """Structured representation of a single briefing item."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    briefing_id: uuid.UUID
    story_id: Optional[uuid.UUID] = None
    article_id: Optional[uuid.UUID] = None
    position: int = 0
    briefing_type: str = Field(
        default=BriefingType.NEW.value,
        description="NEW | UPDATED | FOLLOW_UP | IMPORTANT | FOR_YOU | DISCOVERY",
    )
    headline: str
    summary: Optional[str] = None
    reason: Optional[str] = Field(
        default=None, description="User-facing explanation of why this story is in the briefing."
    )
    importance: float = 0.5
    primary_category: Optional[str] = "GENERAL"
    topics: List[str] = Field(default_factory=list)
    source_name: Optional[str] = "Independent Source"
    source_count: int = 1
    independent_source_count: int = 1
    reading_time_minutes: int = 3
    published_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    url: Optional[str] = None
    top_image_url: Optional[str] = None
    is_read: bool = False
    is_developing: bool = False
    meaningful_update_score: Optional[float] = None
    created_at: Optional[datetime] = None


class NewsBriefingResponse(BaseModel):
    """Complete personalized news briefing snapshot."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    edition_id: Optional[uuid.UUID] = None
    briefing_date: str
    daypart: str = Daypart.MORNING.value
    title: str = "YOUR DAILY BRIEFING"
    greeting: str = "GOOD MORNING"
    intro: Optional[str] = None
    status: str = BriefingStatus.READY.value
    version: int = 1
    is_caught_up: bool = False
    total_items: int = 0
    top_items: List[BriefingItemResponse] = Field(
        default_factory=list, description="Primary 'Things to Know' highlight stories"
    )
    what_changed: List[BriefingItemResponse] = Field(
        default_factory=list, description="Updated and Follow-up stories since last visit"
    )
    items: List[BriefingItemResponse] = Field(
        default_factory=list, description="All briefing items in editorial order"
    )
    generated_at: datetime
    last_session_at: Optional[datetime] = None


class BriefingHistorySummary(BaseModel):
    """Brief summary item for historical briefings list."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    briefing_date: str
    daypart: str
    title: str
    status: str
    version: int
    total_items: int
    is_caught_up: bool
    generated_at: datetime


class BriefingStatusResponse(BaseModel):
    """Status and freshness info for a user's briefing."""
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    briefing_date: str
    daypart: str
    status: str
    is_stale: bool
    latest_version: int
    staleness_reasons: List[str] = Field(default_factory=list)


class GenerateBriefingRequest(BaseModel):
    """Payload to trigger on-demand briefing generation."""
    briefing_date: Optional[str] = Field(
        default=None, description="Target date (YYYY-MM-DD), defaults to local date"
    )
    daypart: Optional[str] = Field(
        default=None, description="MORNING | MIDDAY | EVENING, defaults to current time-of-day"
    )
    force_refresh: bool = Field(
        default=False, description="Generate a new version even if one exists"
    )


class StartSessionRequest(BaseModel):
    """Request to begin a user news session."""
    client_info: Optional[str] = None


class StartSessionResponse(BaseModel):
    """Response returned upon starting a session."""
    session_id: uuid.UUID
    started_at: datetime


class SessionHeartbeatRequest(BaseModel):
    """Periodic heartbeat from the reading interface."""
    stories_viewed_delta: int = 0
    articles_opened_delta: int = 0
    has_meaningful_activity: bool = False


class SessionHeartbeatResponse(BaseModel):
    session_id: uuid.UUID
    is_active: bool
    last_heartbeat_at: datetime


class EndSessionResponse(BaseModel):
    session_id: uuid.UUID
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    stories_viewed: int
    articles_opened: int
    meaningful_activity: bool
