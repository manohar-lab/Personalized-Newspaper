"""session_service.py — Phase 18 User News Session Tracking."""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.briefings.models import NewsSession
from app.models.reading_history import ReadingHistory

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class NewsSessionService:
    """Manages user news browsing sessions and discovers the user's last interaction baseline."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def start_session(self, user_id: uuid.UUID) -> NewsSession:
        """Starts a new news reading session."""
        now = utc_now()
        news_sess = NewsSession(
            user_id=user_id,
            started_at=now,
            last_heartbeat_at=now,
            stories_viewed=0,
            articles_opened=0,
            meaningful_activity=False,
        )
        self.session.add(news_sess)
        await self.session.commit()
        await self.session.refresh(news_sess)
        return news_sess

    async def record_heartbeat(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        stories_viewed_delta: int = 0,
        articles_opened_delta: int = 0,
        has_meaningful_activity: bool = False,
    ) -> Optional[NewsSession]:
        """Updates an active session with heartbeats and activity signals."""
        stmt = select(NewsSession).where(
            NewsSession.id == session_id,
            NewsSession.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        news_sess = res.scalars().first()
        if not news_sess:
            return None

        news_sess.last_heartbeat_at = utc_now()
        news_sess.stories_viewed += max(0, stories_viewed_delta)
        news_sess.articles_opened += max(0, articles_opened_delta)

        if has_meaningful_activity or news_sess.stories_viewed >= 2 or news_sess.articles_opened >= 1:
            news_sess.meaningful_activity = True

        await self.session.commit()
        await self.session.refresh(news_sess)
        return news_sess

    async def end_session(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[NewsSession]:
        """Closes a news reading session."""
        stmt = select(NewsSession).where(
            NewsSession.id == session_id,
            NewsSession.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        news_sess = res.scalars().first()
        if not news_sess:
            return None

        now = utc_now()
        news_sess.ended_at = now
        news_sess.last_heartbeat_at = now

        started_dt = ensure_utc(news_sess.started_at) or now
        duration_sec = (now - started_dt).total_seconds()
        if duration_sec >= 20 or news_sess.stories_viewed >= 2 or news_sess.articles_opened >= 1:
            news_sess.meaningful_activity = True

        await self.session.commit()
        await self.session.refresh(news_sess)
        return news_sess

    async def get_last_meaningful_session_time(
        self, user_id: uuid.UUID, current_session_id: Optional[uuid.UUID] = None
    ) -> Optional[datetime]:
        """
        Finds the timestamp when the user last meaningfully read or browsed the news.
        Used to determine what has changed since their last visit.
        """
        # 1. Check previous meaningful NewsSessions
        stmt = select(NewsSession).where(
            NewsSession.user_id == user_id,
            NewsSession.meaningful_activity == True,
        )
        if current_session_id:
            stmt = stmt.where(NewsSession.id != current_session_id)
        stmt = stmt.order_by(desc(NewsSession.started_at)).limit(1)

        res = await self.session.execute(stmt)
        last_sess = res.scalars().first()
        if last_sess:
            # Use the session end time or started time
            return ensure_utc(last_sess.ended_at or last_sess.started_at)

        # 2. Fallback to ReadingHistory (Phase 12)
        read_stmt = (
            select(ReadingHistory.updated_at)
            .where(ReadingHistory.user_id == user_id)
            .order_by(desc(ReadingHistory.updated_at))
            .limit(1)
        )
        read_res = await self.session.execute(read_stmt)
        last_read_dt = read_res.scalars().first()
        if last_read_dt:
            return ensure_utc(last_read_dt)

        # 3. Default fallback: 24 hours ago
        return utc_now() - timedelta(hours=24)
