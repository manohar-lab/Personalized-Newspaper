import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.article import ArticleBase, TopicSummary

class EditionInfo(BaseModel):
    date: str
    title: str
    subtitle: Optional[str] = None

class UserSummary(BaseModel):
    id: uuid.UUID
    name: str
    email: str

class NewspaperSection(BaseModel):
    topic: TopicSummary
    total_articles: int
    articles: List[ArticleBase]

class NewspaperResponse(BaseModel):
    edition: EditionInfo
    user: UserSummary
    curation_summary: str
    has_interests: bool
    featured_article: Optional[ArticleBase] = None
    sections: List[NewspaperSection] = []
