import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.article import Article
from app.repositories.article_repository import ArticleRepository
from app.repositories.action_repository import ActionRepository
from app.schemas.article import (
    TopicSummary,
    ArticleBase,
    ArticleDetailResponse,
    ArticleListResponse,
)

class ArticleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.article_repo = ArticleRepository(session)
        self.action_repo = ActionRepository(session)

    def _map_article_to_schema(
        self,
        article: Article,
        user_actions: Optional[set] = None,
        relevance_score: Optional[float] = None,
    ) -> ArticleBase:
        actions = user_actions or set()
        return ArticleBase(
            id=article.id,
            title=article.title,
            slug=article.slug,
            description=article.description,
            content=article.content,
            source_name=article.source_name,
            source_url=article.source_url,
            author=article.author,
            image_url=article.image_url,
            published_at=article.published_at,
            created_at=article.created_at,
            reading_time_minutes=article.reading_time_minutes,
            status=article.status,
            language=article.language,
            is_full_text_available=article.is_full_text_available,
            topics=[
                TopicSummary(id=t.id, name=t.name, slug=t.slug)
                for t in article.topics
            ],
            is_saved="SAVE" in actions,
            is_liked="LIKE" in actions,
            is_not_interested="NOT_INTERESTED" in actions,
            relevance_score=relevance_score,
        )

    async def get_published_articles(
        self,
        topic_slug: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
        current_user: Optional[User] = None,
    ) -> ArticleListResponse:
        page = max(1, page)
        limit = min(100, max(1, limit))

        articles, total = await self.article_repo.get_published_articles(
            topic_slug=topic_slug, page=page, limit=limit
        )

        actions_map = {}
        if current_user and articles:
            article_ids = [a.id for a in articles]
            actions_map = await self.action_repo.get_user_actions_map(
                current_user.id, article_ids
            )

        items = [
            self._map_article_to_schema(
                art, user_actions=actions_map.get(art.id, set())
            )
            for art in articles
        ]

        total_pages = (total + limit - 1) // limit if limit > 0 else 0

        return ArticleListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    async def get_article_detail(
        self, article_id: uuid.UUID, current_user: Optional[User] = None
    ) -> ArticleDetailResponse:
        article = await self.article_repo.get_article_by_id(
            article_id, only_published=True
        )
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found or not published",
            )

        user_actions = set()
        if current_user:
            user_actions = await self.action_repo.get_user_actions_for_article(
                current_user.id, article.id
            )

        # Fetch related articles
        topic_ids = [t.id for t in article.topics]
        related_db_articles = await self.article_repo.get_related_articles(
            article_id=article.id, topic_ids=topic_ids, limit=4
        )

        related_actions_map = {}
        if current_user and related_db_articles:
            related_ids = [r.id for r in related_db_articles]
            related_actions_map = await self.action_repo.get_user_actions_map(
                current_user.id, related_ids
            )

        related_items = [
            self._map_article_to_schema(
                r_art, user_actions=related_actions_map.get(r_art.id, set())
            )
            for r_art in related_db_articles
        ]

        base = self._map_article_to_schema(article, user_actions=user_actions)
        return ArticleDetailResponse(
            **base.model_dump(),
            related_articles=related_items,
        )

    async def get_featured_article(
        self, current_user: Optional[User] = None
    ) -> ArticleBase:
        article = await self.article_repo.get_featured_article()
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No featured articles available",
            )

        user_actions = set()
        if current_user:
            user_actions = await self.action_repo.get_user_actions_for_article(
                current_user.id, article.id
            )

        return self._map_article_to_schema(article, user_actions=user_actions)
