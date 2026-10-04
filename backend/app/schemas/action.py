import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.article import ArticleBase

class UserActionResponse(BaseModel):
    success: bool
    action: str
    article_id: uuid.UUID
    message: str

class SavedArticleItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    article: ArticleBase
    saved_at: datetime

class SavedArticlesListResponse(BaseModel):
    items: List[SavedArticleItem]
    total: int
    page: int
    limit: int
    total_pages: int
