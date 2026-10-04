import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.article import Article, article_topics
from app.models.topic import Topic

class ArticleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_published_articles(
        self,
        topic_slug: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
    ) -> Tuple[List[Article], int]:
        """Fetch published articles with optional topic filter and pagination."""
        offset = (page - 1) * limit

        base_query = (
            select(Article)
            .options(selectinload(Article.topics))
            .where(Article.status == "PUBLISHED")
        )
        count_query = (
            select(func.count(func.distinct(Article.id)))
            .where(Article.status == "PUBLISHED")
        )

        if topic_slug:
            base_query = base_query.join(Article.topics).where(Topic.slug == topic_slug)
            count_query = count_query.join(Article.topics).where(Topic.slug == topic_slug)

        # Count total
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Fetch items
        items_query = (
            base_query
            .order_by(desc(Article.published_at))
            .offset(offset)
            .limit(limit)
        )
        items_result = await self.session.execute(items_query)
        items = list(items_result.scalars().all())

        return items, total

    async def get_article_by_id(
        self, article_id: uuid.UUID, only_published: bool = True
    ) -> Optional[Article]:
        """Fetch an article by UUID."""
        query = (
            select(Article)
            .options(selectinload(Article.topics))
            .where(Article.id == article_id)
        )
        if only_published:
            query = query.where(Article.status == "PUBLISHED")

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_featured_article(self) -> Optional[Article]:
        """Fetch the most recent published article as default featured story."""
        query = (
            select(Article)
            .options(selectinload(Article.topics))
            .where(Article.status == "PUBLISHED")
            .order_by(desc(Article.published_at))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_published(self) -> List[Article]:
        """Fetch all published articles with loaded topics for ranking and grouping."""
        query = (
            select(Article)
            .options(selectinload(Article.topics))
            .where(Article.status == "PUBLISHED")
            .order_by(desc(Article.published_at))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_related_articles(
        self, article_id: uuid.UUID, topic_ids: List[uuid.UUID], limit: int = 4
    ) -> List[Article]:
        """
        Find related articles sharing topics with current article.
        Sorted by:
        1. Number of shared topics (descending)
        2. Publication date (descending)
        """
        if not topic_ids:
            # Fallback to recent articles excluding this one
            fallback_query = (
                select(Article)
                .options(selectinload(Article.topics))
                .where(Article.status == "PUBLISHED", Article.id != article_id)
                .order_by(desc(Article.published_at))
                .limit(limit)
            )
            res = await self.session.execute(fallback_query)
            return list(res.scalars().all())

        # Count shared topics using group by
        shared_count_col = func.count(article_topics.c.topic_id).label("shared_topics_count")

        subq = (
            select(
                article_topics.c.article_id,
                shared_count_col,
            )
            .where(
                article_topics.c.topic_id.in_(topic_ids),
                article_topics.c.article_id != article_id,
            )
            .group_by(article_topics.c.article_id)
            .subquery()
        )

        query = (
            select(Article)
            .options(selectinload(Article.topics))
            .join(subq, Article.id == subq.c.article_id)
            .where(Article.status == "PUBLISHED")
            .order_by(
                desc(subq.c.shared_topics_count),
                desc(Article.published_at),
            )
            .limit(limit)
        )

        result = await self.session.execute(query)
        articles = list(result.scalars().all())

        if len(articles) < limit:
            # Backfill with other recent published articles if needed
            existing_ids = {a.id for a in articles} | {article_id}
            backfill_needed = limit - len(articles)
            backfill_query = (
                select(Article)
                .options(selectinload(Article.topics))
                .where(
                    Article.status == "PUBLISHED",
                    ~Article.id.in_(existing_ids),
                )
                .order_by(desc(Article.published_at))
                .limit(backfill_needed)
            )
            backfill_res = await self.session.execute(backfill_query)
            articles.extend(list(backfill_res.scalars().all()))

        return articles
