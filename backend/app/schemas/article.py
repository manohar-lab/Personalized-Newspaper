import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class TopicSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str

class ArticleBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    description: Optional[str] = None
    content: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    canonical_url: Optional[str] = None
    source_id: Optional[uuid.UUID] = None
    feed_id: Optional[uuid.UUID] = None
    ingestion_method: str = "MANUAL"
    author: Optional[str] = None
    image_url: Optional[str] = None
    published_at: datetime
    created_at: datetime
    reading_time_minutes: int
    status: str
    language: str = "en"
    is_full_text_available: bool = True
    topics: List[TopicSummary] = []
    is_saved: Optional[bool] = False
    is_liked: Optional[bool] = False
    is_not_interested: Optional[bool] = False
    relevance_score: Optional[float] = None

class ArticleDetailResponse(ArticleBase):
    related_articles: List[ArticleBase] = []

class ArticleListResponse(BaseModel):
    items: List[ArticleBase]
    total: int
    page: int
    limit: int
    total_pages: int
