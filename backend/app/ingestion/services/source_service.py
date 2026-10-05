import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.source import NewsSource
from app.models.feed import NewsFeed
from app.schemas.news import SourceCreate, FeedCreate


class SourceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_sources(self, is_active: Optional[bool] = None) -> List[NewsSource]:
        stmt = select(NewsSource).options(selectinload(NewsSource.feeds)).order_by(NewsSource.name)
        if is_active is not None:
            stmt = stmt.where(NewsSource.is_active == is_active)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_source_by_id(self, source_id: uuid.UUID) -> Optional[NewsSource]:
        stmt = (
            select(NewsSource)
            .options(selectinload(NewsSource.feeds))
            .where(NewsSource.id == source_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_source_by_slug(self, slug: str) -> Optional[NewsSource]:
        stmt = (
            select(NewsSource)
            .options(selectinload(NewsSource.feeds))
            .where(NewsSource.slug == slug)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_source(self, data: SourceCreate) -> NewsSource:
        source = NewsSource(
            id=uuid.uuid4(),
            name=data.name,
            slug=data.slug,
            website_url=data.website_url,
            description=data.description,
            logo_url=data.logo_url,
            is_active=data.is_active,
        )
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def get_feeds(
        self,
        is_active: Optional[bool] = None,
        source_id: Optional[uuid.UUID] = None,
    ) -> List[NewsFeed]:
        stmt = (
            select(NewsFeed)
            .options(
                selectinload(NewsFeed.source),
                selectinload(NewsFeed.default_topic),
            )
            .order_by(NewsFeed.name)
        )
        if is_active is not None:
            stmt = stmt.where(NewsFeed.is_active == is_active)
        if source_id is not None:
            stmt = stmt.where(NewsFeed.source_id == source_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_feed_by_id(self, feed_id: uuid.UUID) -> Optional[NewsFeed]:
        stmt = (
            select(NewsFeed)
            .options(
                selectinload(NewsFeed.source),
                selectinload(NewsFeed.default_topic),
            )
            .where(NewsFeed.id == feed_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_feed(self, data: FeedCreate) -> NewsFeed:
        feed = NewsFeed(
            id=uuid.uuid4(),
            source_id=data.source_id,
            name=data.name,
            feed_url=data.feed_url,
            feed_type=data.feed_type.upper(),
            language=data.language,
            is_active=data.is_active,
            default_topic_id=data.default_topic_id,
        )
        self.session.add(feed)
        await self.session.commit()
        await self.session.refresh(feed)
        return feed

    async def update_feed_status(
        self,
        feed_id: uuid.UUID,
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        feed = await self.get_feed_by_id(feed_id)
        if not feed:
            return

        now = datetime.now(timezone.utc)
        feed.last_fetched_at = now
        if success:
            feed.last_success_at = now
            feed.last_error = None
        else:
            feed.last_failure_at = now
            feed.last_error = error_message

        await self.session.commit()
