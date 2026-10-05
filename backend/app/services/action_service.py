import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.action import ActionType
from app.repositories.action_repository import ActionRepository
from app.repositories.article_repository import ArticleRepository
from app.schemas.action import (
    UserActionResponse,
    SavedArticleItem,
    SavedArticlesListResponse,
)
from app.schemas.article import ArticleBase, TopicSummary

from app.learning.agent import InterestLearningAgent

class ActionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.action_repo = ActionRepository(session)
        self.article_repo = ArticleRepository(session)
        self.learning_agent = InterestLearningAgent(session)

    async def _validate_article_exists(self, article_id: uuid.UUID):
        article = await self.article_repo.get_article_by_id(article_id, only_published=False)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Article not found",
            )
        return article

    async def save_article(
        self, user_id: uuid.UUID, article_id: uuid.UUID
    ) -> UserActionResponse:
        await self._validate_article_exists(article_id)
        await self.action_repo.add_action(
            user_id=user_id, article_id=article_id, action=ActionType.SAVE.value
        )
        # Log learning event
        await self.learning_agent.process_event(
            user_id=user_id,
            event_type="ARTICLE_SAVE",
            article_id=article_id,
            commit=True,
        )
        return UserActionResponse(
            success=True,
            action=ActionType.SAVE.value,
            article_id=article_id,
            message="Article saved successfully",
        )

    async def unsave_article(
        self, user_id: uuid.UUID, article_id: uuid.UUID
    ) -> UserActionResponse:
        await self._validate_article_exists(article_id)
        await self.action_repo.remove_action(
            user_id=user_id, article_id=article_id, action=ActionType.SAVE.value
        )
        return UserActionResponse(
            success=True,
            action=ActionType.SAVE.value,
            article_id=article_id,
            message="Article removed from saved",
        )

    async def like_article(
        self, user_id: uuid.UUID, article_id: uuid.UUID
    ) -> UserActionResponse:
        await self._validate_article_exists(article_id)
        await self.action_repo.add_action(
            user_id=user_id, article_id=article_id, action=ActionType.LIKE.value
        )
        # Log learning event
        await self.learning_agent.process_event(
            user_id=user_id,
            event_type="ARTICLE_LIKE",
            article_id=article_id,
            commit=True,
        )
        return UserActionResponse(
            success=True,
            action=ActionType.LIKE.value,
            article_id=article_id,
            message="Article liked",
        )

    async def mark_not_interested(
        self, user_id: uuid.UUID, article_id: uuid.UUID
    ) -> UserActionResponse:
        await self._validate_article_exists(article_id)
        await self.action_repo.add_action(
            user_id=user_id, article_id=article_id, action=ActionType.NOT_INTERESTED.value
        )
        # Log learning event
        await self.learning_agent.process_event(
            user_id=user_id,
            event_type="ARTICLE_NOT_INTERESTED",
            article_id=article_id,
            commit=True,
        )
        return UserActionResponse(
            success=True,
            action=ActionType.NOT_INTERESTED.value,
            article_id=article_id,
            message="Marked as not interested",
        )

    async def get_saved_articles(
        self, user_id: uuid.UUID, page: int = 1, limit: int = 10
    ) -> SavedArticlesListResponse:
        page = max(1, page)
        limit = min(100, max(1, limit))

        results, total = await self.action_repo.get_saved_articles(
            user_id=user_id, page=page, limit=limit
        )

        article_ids = [art.id for _, art in results]
        actions_map = await self.action_repo.get_user_actions_map(user_id, article_ids)

        items = []
        for action_rec, art in results:
            actions = actions_map.get(art.id, set())
            art_schema = ArticleBase(
                id=art.id,
                title=art.title,
                slug=art.slug,
                description=art.description,
                content=art.content,
                source_name=art.source_name,
                source_url=art.source_url,
                author=art.author,
                image_url=art.image_url,
                published_at=art.published_at,
                created_at=art.created_at,
                reading_time_minutes=art.reading_time_minutes,
                status=art.status,
                language=art.language,
                is_full_text_available=art.is_full_text_available,
                topics=[
                    TopicSummary(id=t.id, name=t.name, slug=t.slug)
                    for t in art.topics
                ],
                is_saved=True,
                is_liked="LIKE" in actions,
                is_not_interested="NOT_INTERESTED" in actions,
            )
            items.append(
                SavedArticleItem(
                    id=action_rec.id,
                    article=art_schema,
                    saved_at=action_rec.created_at,
                )
            )

        total_pages = (total + limit - 1) // limit if limit > 0 else 0

        return SavedArticlesListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )
