"""reading.py — Phase 12 Reading History & Session Tracking Schemas."""
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.article import ArticleBase


class ReadingStartRequest(BaseModel):
    """Payload to initiate a reading session."""
    article_id: uuid.UUID
    source_context: Optional[str] = Field(
        default="DIRECT",
        description="Source context: NEWSPAPER | SEARCH | SAVED | DIRECT | OTHER",
    )


class ReadingStartResponse(BaseModel):
    """Confirmed initiated reading session."""
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    article_id: uuid.UUID
    started_at: datetime
    source_context: Optional[str] = "DIRECT"


class ReadingHeartbeatRequest(BaseModel):
    """Periodic reading activity heartbeat."""
    session_id: uuid.UUID
    scroll_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Approximate current scroll percentage"
    )
    active_duration_seconds: Optional[float] = Field(
        default=None, description="Optional active visible elapsed time"
    )


class ReadingHeartbeatResponse(BaseModel):
    """Heartbeat acknowledgement and progress state."""
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    is_active: bool
    total_session_duration: float
    max_scroll_percentage: float
    is_completed: bool


class ReadingEndRequest(BaseModel):
    """Payload to conclude an active reading session."""
    session_id: uuid.UUID
    article_id: uuid.UUID
    completion_percentage: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Final completion percentage"
    )
    max_scroll_percentage: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Maximum scroll depth reached"
    )


class ReadingEndResponse(BaseModel):
    """Concluded reading session metrics."""
    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    article_id: uuid.UUID
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    completion_percentage: float
    max_scroll_percentage: float
    engagement_score: float
    engagement_level: str
    is_completed: bool


class ReadingHistoryItemResponse(BaseModel):
    """Aggregate history record for a single user + article."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    article_id: uuid.UUID
    article: ArticleBase
    first_opened_at: datetime
    last_opened_at: datetime
    last_read_at: datetime
    open_count: int
    total_duration_seconds: float
    max_scroll_percentage: float
    average_scroll_percentage: float
    completion_count: int
    last_completion_percentage: float
    engagement_score: float
    engagement_level: str  # BOUNCED | LOW | MEDIUM | HIGH | DEEP


class ReadingHistoryListResponse(BaseModel):
    """Paginated list of reading history."""
    items: List[ReadingHistoryItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ContinueReadingItemResponse(BaseModel):
    """An incomplete article queued for continuous reading."""
    article_id: uuid.UUID
    article: ArticleBase
    last_read_at: datetime
    progress_percentage: float
    max_scroll_percentage: float
    total_duration_seconds: float
    engagement_level: str


class ContinueReadingListResponse(BaseModel):
    """List of articles for Continue Reading shelf."""
    items: List[ContinueReadingItemResponse]
    total: int


class ReadingMetricsResponse(BaseModel):
    """Development analytics for reading engagement intelligence."""
    average_reading_duration_seconds: float
    completion_rate_percentage: float
    average_scroll_depth_percentage: float
    bounce_rate_percentage: float
    deep_read_rate_percentage: float
    total_articles_completed: int
    total_sessions_count: int
    total_reading_history_count: int


class ArticleReadingStateResponse(BaseModel):
    """Article reading state for resuming and progress indicator."""
    model_config = ConfigDict(from_attributes=True)

    article_id: uuid.UUID
    has_history: bool = False
    last_scroll_percentage: float = 0.0
    last_completion_percentage: float = 0.0
    is_completed: bool = False
    total_duration_seconds: float = 0.0
    open_count: int = 0
    last_read_at: Optional[datetime] = None

