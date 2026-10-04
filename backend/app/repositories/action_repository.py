import uuid
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import select, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.action import UserArticleAction, ActionType
from app.models.article import Article

class ActionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_action(
        self, user_id: uuid.UUID, article_id: uuid.UUID, action: str
    ) -> UserArticleAction:
        """Add an action for a user on an article idempotently."""
        stmt = select(UserArticleAction).where(
            UserArticleAction.user_id == user_id,
            UserArticleAction.article_id == article_id,
            UserArticleAction.action == action,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        action_record = UserArticleAction(
            user_id=user_id,
            article_id=article_id,
            action=action,
        )
        self.session.add(action_record)
        await self.session.commit()
        await self.session.refresh(action_record)
        return action_record

    async def remove_action(
        self, user_id: uuid.UUID, article_id: uuid.UUID, action: str
    ) -> bool:
        """Remove a specific action record for a user on an article."""
        stmt = delete(UserArticleAction).where(
            UserArticleAction.user_id == user_id,
            UserArticleAction.article_id == article_id,
            UserArticleAction.action == action,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_user_actions_for_article(
        self, user_id: uuid.UUID, article_id: uuid.UUID
    ) -> Set[str]:
        """Fetch all action types performed by user on a given article."""
        stmt = select(UserArticleAction.action).where(
            UserArticleAction.user_id == user_id,
            UserArticleAction.article_id == article_id,
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def get_user_actions_map(
        self, user_id: uuid.UUID, article_ids: List[uuid.UUID]
    ) -> Dict[uuid.UUID, Set[str]]:
        """Fetch all action types for a list of articles for the user."""
        if not article_ids:
            return {}

        stmt = select(UserArticleAction.article_id, UserArticleAction.action).where(
            UserArticleAction.user_id == user_id,
            UserArticleAction.article_id.in_(article_ids),
        )
        result = await self.session.execute(stmt)
        action_map: Dict[uuid.UUID, Set[str]] = {aid: set() for aid in article_ids}
        for art_id, act in result.all():
            if art_id in action_map:
                action_map[art_id].add(act)
        return action_map

    async def get_saved_articles(
        self, user_id: uuid.UUID, page: int = 1, limit: int = 10
    ) -> Tuple[List[Tuple[UserArticleAction, Article]], int]:
        """Fetch saved articles for user with pagination."""
        offset = (page - 1) * limit

        base_query = (
            select(UserArticleAction, Article)
            .join(Article, UserArticleAction.article_id == Article.id)
            .options(selectinload(Article.topics))
            .where(
                UserArticleAction.user_id == user_id,
                UserArticleAction.action == ActionType.SAVE.value,
                Article.status == "PUBLISHED",
            )
        )

        count_query = (
            select(func.count(UserArticleAction.id))
            .join(Article, UserArticleAction.article_id == Article.id)
            .where(
                UserArticleAction.user_id == user_id,
                UserArticleAction.action == ActionType.SAVE.value,
                Article.status == "PUBLISHED",
            )
        )

        count_res = await self.session.execute(count_query)
        total = count_res.scalar() or 0

        items_query = (
            base_query
            .order_by(desc(UserArticleAction.created_at))
            .offset(offset)
            .limit(limit)
        )
        items_res = await self.session.execute(items_query)
        items = list(items_res.all())

        return items, total
