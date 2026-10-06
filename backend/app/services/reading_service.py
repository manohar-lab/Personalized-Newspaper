"""reading_service.py — Phase 12 Reading History & Engagement Intelligence Service.

Coordinates session lifecycle, heartbeats, scroll depth tracking, aggregate reading history,
continue reading queries, retention cleanup, and unified interest learning agent signals.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import select, func, delete, and_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import logger
from app.models.article import Article
from app.models.user import User
from app.models.action import UserArticleAction
from app.models.reading_history import ReadingHistory
from app.learning.models import ReadingSession
from app.learning.engagement import EngagementIntelligence
from app.learning.agent import InterestLearningAgent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_tz_aware(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return utc_now()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ReadingService:
    """Service managing reading sessions, heartbeats, aggregate history, and engagement analytics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_reading_session(
        self,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
        source_context: Optional[str] = "DIRECT",
    ) -> ReadingSession:
        """
        Record ARTICLE_OPEN and begin a server-timestamped reading session.
        Upserts the aggregate reading_history record for this (user, article) pair.
        """
        now = utc_now()

        # 1. Fetch article to verify existence and reading time
        stmt_art = select(Article).where(Article.id == article_id)
        res_art = await self.db.execute(stmt_art)
        art = res_art.scalar_one_or_none()
        if not art:
            raise ValueError(f"Article with id {article_id} not found")

        # 2. Create reading session
        session_id = uuid.uuid4()
        session_obj = ReadingSession(
            id=session_id,
            user_id=user_id,
            article_id=article_id,
            started_at=now,
            max_scroll_percentage=0.0,
            completion_percentage=0.0,
            is_completed=False,
            source_context=source_context or "DIRECT",
            last_heartbeat_at=now,
            created_at=now,
        )
        self.db.add(session_obj)

        # 3. Upsert aggregate reading_history
        stmt_hist = select(ReadingHistory).where(
            ReadingHistory.user_id == user_id,
            ReadingHistory.article_id == article_id,
        )
        res_hist = await self.db.execute(stmt_hist)
        history = res_hist.scalar_one_or_none()

        if history:
            history.open_count += 1
            history.last_opened_at = now
            history.last_read_at = now
            history.updated_at = now
        else:
            history = ReadingHistory(
                id=uuid.uuid4(),
                user_id=user_id,
                article_id=article_id,
                first_opened_at=now,
                last_opened_at=now,
                open_count=1,
                total_duration_seconds=0.0,
                max_scroll_percentage=0.0,
                average_scroll_percentage=0.0,
                completion_count=0,
                last_completion_percentage=0.0,
                last_read_at=now,
                engagement_score=0.0,
                engagement_level="BOUNCED",
                created_at=now,
                updated_at=now,
            )
            self.db.add(history)

        # 4. Log non-spammy initial open behavior event
        agent = InterestLearningAgent(self.db)
        await agent.process_event(
            user_id=user_id,
            event_type="ARTICLE_OPEN",
            article_id=article_id,
            value=settings.WEIGHT_ARTICLE_OPEN,
            metadata={"source_context": source_context, "session_id": str(session_id)},
            commit=False,
        )

        await self.db.commit()
        await self.db.refresh(session_obj)
        return session_obj

    async def record_heartbeat(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        scroll_percentage: float,
        active_duration_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Process a periodic reading heartbeat (every 15-30s).
        Calculates server-authoritative elapsed active duration, updates scroll depth and completion.
        """
        now = utc_now()
        stmt = (
            select(ReadingSession)
            .options(selectinload(ReadingSession.article))
            .where(
                ReadingSession.id == session_id,
                ReadingSession.user_id == user_id,
            )
        )
        res = await self.db.execute(stmt)
        session_obj = res.scalar_one_or_none()
        if not session_obj:
            raise ValueError(f"Reading session {session_id} not found for user {user_id}")

        started_at = ensure_tz_aware(session_obj.started_at)
        elapsed = max(0.0, (now - started_at).total_seconds())

        # Respect active duration from visibility tracking without trusting arbitrary values
        if active_duration_seconds is not None and active_duration_seconds >= 0:
            duration = min(elapsed, float(active_duration_seconds))
        else:
            duration = elapsed

        session_obj.duration_seconds = round(duration, 2)
        session_obj.last_heartbeat_at = now

        # Update max scroll percentage
        clamped_scroll = max(0.0, min(100.0, float(scroll_percentage)))
        session_obj.max_scroll_percentage = max(
            session_obj.max_scroll_percentage or 0.0, clamped_scroll
        )

        # Check completion
        expected_seconds = (
            session_obj.article.reading_time_minutes * 60.0
            if session_obj.article
            else 180.0
        )
        calc_comp = max(
            session_obj.completion_percentage or 0.0,
            clamped_scroll,
        )
        session_obj.completion_percentage = round(calc_comp, 2)

        is_completed = (
            session_obj.max_scroll_percentage >= settings.ARTICLE_COMPLETION_THRESHOLD
            and duration >= settings.MINIMUM_MEANINGFUL_READ_SECONDS
        )
        session_obj.is_completed = is_completed

        # Update aggregate reading history
        stmt_hist = select(ReadingHistory).where(
            ReadingHistory.user_id == user_id,
            ReadingHistory.article_id == session_obj.article_id,
        )
        res_hist = await self.db.execute(stmt_hist)
        history = res_hist.scalar_one_or_none()

        if history:
            history.max_scroll_percentage = max(
                history.max_scroll_percentage, session_obj.max_scroll_percentage
            )
            history.last_completion_percentage = max(
                history.last_completion_percentage, session_obj.completion_percentage
            )
            history.last_read_at = now
            history.updated_at = now

            # Check actions (like/save) for score computation
            stmt_acts = select(UserArticleAction.action).where(
                UserArticleAction.user_id == user_id,
                UserArticleAction.article_id == session_obj.article_id,
            )
            res_acts = await self.db.execute(stmt_acts)
            actions = set(res_acts.scalars().all())

            score = EngagementIntelligence.calculate_engagement_score(
                duration_seconds=history.total_duration_seconds + duration,
                expected_reading_seconds=expected_seconds,
                max_scroll_percentage=history.max_scroll_percentage,
                completion_percentage=history.last_completion_percentage,
                open_count=history.open_count,
                is_completed=is_completed or (history.completion_count > 0),
                has_liked="LIKE" in actions,
                has_saved="SAVE" in actions,
            )
            level = EngagementIntelligence.classify_engagement_level(
                duration_seconds=history.total_duration_seconds + duration,
                expected_reading_seconds=expected_seconds,
                max_scroll_percentage=history.max_scroll_percentage,
                completion_percentage=history.last_completion_percentage,
                open_count=history.open_count,
                is_completed=is_completed or (history.completion_count > 0),
            )
            history.engagement_score = score
            history.engagement_level = level

        await self.db.commit()

        return {
            "session_id": session_obj.id,
            "is_active": True,
            "total_session_duration": session_obj.duration_seconds or 0.0,
            "max_scroll_percentage": session_obj.max_scroll_percentage,
            "is_completed": session_obj.is_completed,
        }

    async def end_reading_session(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        article_id: uuid.UUID,
        completion_percentage: Optional[float] = None,
        max_scroll_percentage: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Conclude active reading session, finalize duration, update aggregate history,
        and trigger unified interest learning signal.
        """
        now = utc_now()

        # 1. Fetch or create session
        stmt = (
            select(ReadingSession)
            .options(selectinload(ReadingSession.article))
            .where(
                ReadingSession.id == session_id,
                ReadingSession.user_id == user_id,
            )
        )
        res = await self.db.execute(stmt)
        session_obj = res.scalar_one_or_none()

        if not session_obj:
            session_obj = ReadingSession(
                id=session_id,
                user_id=user_id,
                article_id=article_id,
                started_at=now,
                created_at=now,
            )
            self.db.add(session_obj)

        session_obj.ended_at = now
        started_at = ensure_tz_aware(session_obj.started_at)
        duration = max(0.0, (now - started_at).total_seconds())
        session_obj.duration_seconds = round(duration, 2)

        # 2. Update scroll depth & completion
        if max_scroll_percentage is not None:
            clamped_scroll = max(0.0, min(100.0, float(max_scroll_percentage)))
            session_obj.max_scroll_percentage = max(
                session_obj.max_scroll_percentage or 0.0, clamped_scroll
            )

        # Article reading time estimation
        expected_seconds = 180.0
        if session_obj.article:
            expected_seconds = session_obj.article.reading_time_minutes * 60.0
        else:
            stmt_art = select(Article).where(Article.id == article_id)
            res_art = await self.db.execute(stmt_art)
            art = res_art.scalar_one_or_none()
            if art:
                expected_seconds = art.reading_time_minutes * 60.0

        if completion_percentage is not None:
            calc_comp = max(0.0, min(100.0, float(completion_percentage)))
        else:
            calc_comp = max(
                session_obj.max_scroll_percentage,
                min(100.0, (duration / expected_seconds) * 100.0),
            )

        session_obj.completion_percentage = round(calc_comp, 2)

        # Determine completion flag
        is_completed = bool(
            (session_obj.completion_percentage >= settings.ARTICLE_COMPLETION_THRESHOLD or session_obj.max_scroll_percentage >= settings.ARTICLE_COMPLETION_THRESHOLD)
            and duration >= settings.MINIMUM_MEANINGFUL_READ_SECONDS
        )
        session_obj.is_completed = is_completed

        # 3. Aggregate into reading_history
        stmt_hist = select(ReadingHistory).where(
            ReadingHistory.user_id == user_id,
            ReadingHistory.article_id == article_id,
        )
        res_hist = await self.db.execute(stmt_hist)
        history = res_hist.scalar_one_or_none()

        if not history:
            history = ReadingHistory(
                id=uuid.uuid4(),
                user_id=user_id,
                article_id=article_id,
                first_opened_at=started_at,
                last_opened_at=started_at,
                open_count=1,
                total_duration_seconds=duration,
                max_scroll_percentage=session_obj.max_scroll_percentage,
                average_scroll_percentage=session_obj.max_scroll_percentage,
                completion_count=1 if is_completed else 0,
                last_completion_percentage=session_obj.completion_percentage,
                last_read_at=now,
                engagement_score=0.0,
                engagement_level="BOUNCED",
                created_at=now,
                updated_at=now,
            )
            self.db.add(history)
        else:
            history.total_duration_seconds += duration
            history.max_scroll_percentage = max(
                history.max_scroll_percentage, session_obj.max_scroll_percentage
            )
            history.average_scroll_percentage = round(
                (history.average_scroll_percentage + session_obj.max_scroll_percentage) / 2.0, 2
            )
            if is_completed:
                history.completion_count += 1
            history.last_completion_percentage = session_obj.completion_percentage
            history.last_read_at = now
            history.updated_at = now

        # Fetch likes/saves
        stmt_acts = select(UserArticleAction.action).where(
            UserArticleAction.user_id == user_id,
            UserArticleAction.article_id == article_id,
        )
        res_acts = await self.db.execute(stmt_acts)
        actions = set(res_acts.scalars().all())

        history.engagement_score = EngagementIntelligence.calculate_engagement_score(
            duration_seconds=history.total_duration_seconds,
            expected_reading_seconds=expected_seconds,
            max_scroll_percentage=history.max_scroll_percentage,
            completion_percentage=history.last_completion_percentage,
            open_count=history.open_count,
            is_completed=(history.completion_count > 0),
            has_liked="LIKE" in actions,
            has_saved="SAVE" in actions,
        )
        history.engagement_level = EngagementIntelligence.classify_engagement_level(
            duration_seconds=history.total_duration_seconds,
            expected_reading_seconds=expected_seconds,
            max_scroll_percentage=history.max_scroll_percentage,
            completion_percentage=history.last_completion_percentage,
            open_count=history.open_count,
            is_completed=(history.completion_count > 0),
        )

        # 4. Derive single unified interest learning signal (anti-double-counting)
        signal = EngagementIntelligence.derive_interest_learning_signal(
            engagement_score=history.engagement_score,
            engagement_level=history.engagement_level,
            duration_seconds=duration,
            completion_percentage=session_obj.completion_percentage,
        )

        agent = InterestLearningAgent(self.db)
        await agent.process_event(
            user_id=user_id,
            event_type=signal["event_type"],
            article_id=article_id,
            value=signal["value"],
            metadata={
                "session_id": str(session_id),
                "duration_seconds": duration,
                "completion_percentage": session_obj.completion_percentage,
                "max_scroll_percentage": session_obj.max_scroll_percentage,
                "engagement_level": history.engagement_level,
                "reading_engagement_signal": signal["reading_engagement_signal"],
            },
            commit=False,
        )

        await self.db.commit()
        await self.db.refresh(session_obj)

        return {
            "session_id": session_obj.id,
            "article_id": session_obj.article_id,
            "started_at": session_obj.started_at,
            "ended_at": session_obj.ended_at or now,
            "duration_seconds": session_obj.duration_seconds or duration,
            "completion_percentage": session_obj.completion_percentage or calc_comp,
            "max_scroll_percentage": session_obj.max_scroll_percentage,
            "engagement_score": history.engagement_score,
            "engagement_level": history.engagement_level,
            "is_completed": session_obj.is_completed,
        }

    async def get_user_reading_history(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ReadingHistory], int]:
        """Return paginated private reading history for the authenticated user."""
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        # Count total
        stmt_cnt = select(func.count()).select_from(ReadingHistory).where(
            ReadingHistory.user_id == user_id
        )
        res_cnt = await self.db.execute(stmt_cnt)
        total = res_cnt.scalar() or 0

        # Fetch items
        stmt = (
            select(ReadingHistory)
            .options(
                selectinload(ReadingHistory.article).selectinload(Article.topics),
                selectinload(ReadingHistory.article).selectinload(Article.analysis),
            )
            .where(ReadingHistory.user_id == user_id)
            .order_by(desc(ReadingHistory.last_read_at))
            .offset(offset)
            .limit(page_size)
        )
        res = await self.db.execute(stmt)
        items = res.scalars().all()
        return items, total

    async def get_article_reading_history(
        self,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> Optional[ReadingHistory]:
        """Fetch authenticated user's private history for a specific article."""
        stmt = (
            select(ReadingHistory)
            .options(
                selectinload(ReadingHistory.article).selectinload(Article.topics),
                selectinload(ReadingHistory.article).selectinload(Article.analysis),
            )
            .where(
                ReadingHistory.user_id == user_id,
                ReadingHistory.article_id == article_id,
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_continue_reading(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> List[ReadingHistory]:
        """
        Return started but uncompleted articles for the Continue Reading shelf.
        Filters for articles with progress > 0% but < 85% completion.
        """
        stmt = (
            select(ReadingHistory)
            .options(
                selectinload(ReadingHistory.article).selectinload(Article.topics),
                selectinload(ReadingHistory.article).selectinload(Article.analysis),
            )
            .where(
                ReadingHistory.user_id == user_id,
                ReadingHistory.completion_count == 0,
                ReadingHistory.last_completion_percentage < settings.ARTICLE_COMPLETION_THRESHOLD,
                (
                    (ReadingHistory.max_scroll_percentage > 5.0)
                    | (ReadingHistory.total_duration_seconds >= settings.MINIMUM_MEANINGFUL_READ_SECONDS)
                ),
            )
            .order_by(desc(ReadingHistory.last_read_at))
            .limit(max(1, min(50, limit)))
        )
        res = await self.db.execute(stmt)
        return res.scalars().all()

    async def cleanup_old_reading_history(
        self,
        retention_days: Optional[int] = None,
    ) -> Dict[str, int]:
        """Clean up reading history and sessions older than retention threshold."""
        days = retention_days if retention_days is not None else settings.READING_HISTORY_RETENTION_DAYS
        cutoff = utc_now() - timedelta(days=days)

        # Delete old sessions
        stmt_sess = delete(ReadingSession).where(ReadingSession.started_at < cutoff)
        res_sess = await self.db.execute(stmt_sess)

        # Delete old history
        stmt_hist = delete(ReadingHistory).where(ReadingHistory.last_read_at < cutoff)
        res_hist = await self.db.execute(stmt_hist)

        await self.db.commit()
        logger.info(
            f"Reading history retention cleanup: {res_sess.rowcount} sessions and {res_hist.rowcount} history records removed (older than {days} days)."
        )
        return {
            "sessions_deleted": res_sess.rowcount,
            "history_deleted": res_hist.rowcount,
            "retention_days": days,
        }

    async def get_reading_metrics(self) -> Dict[str, Any]:
        """Calculate development-level engagement intelligence analytics."""
        # Total counts
        stmt_h_cnt = select(func.count()).select_from(ReadingHistory)
        res_h_cnt = await self.db.execute(stmt_h_cnt)
        total_hist = res_h_cnt.scalar() or 0

        stmt_s_cnt = select(func.count()).select_from(ReadingSession)
        res_s_cnt = await self.db.execute(stmt_s_cnt)
        total_sess = res_s_cnt.scalar() or 0

        if total_hist == 0:
            return {
                "average_reading_duration_seconds": 0.0,
                "completion_rate_percentage": 0.0,
                "average_scroll_depth_percentage": 0.0,
                "bounce_rate_percentage": 0.0,
                "deep_read_rate_percentage": 0.0,
                "total_articles_completed": 0,
                "total_sessions_count": total_sess,
                "total_reading_history_count": total_hist,
            }

        stmt_agg = select(
            func.avg(ReadingHistory.total_duration_seconds),
            func.avg(ReadingHistory.max_scroll_percentage),
            func.sum(case((ReadingHistory.completion_count > 0, 1), else_=0)),
            func.sum(case((ReadingHistory.engagement_level == "BOUNCED", 1), else_=0)),
            func.sum(case((ReadingHistory.engagement_level == "DEEP", 1), else_=0)),
        ).select_from(ReadingHistory)

        res_agg = await self.db.execute(stmt_agg)
        avg_dur, avg_scroll, total_comp, total_bounced, total_deep = res_agg.first()

        avg_dur = float(avg_dur or 0.0)
        avg_scroll = float(avg_scroll or 0.0)
        total_comp = int(total_comp or 0)
        total_bounced = int(total_bounced or 0)
        total_deep = int(total_deep or 0)

        comp_rate = (total_comp / total_hist) * 100.0 if total_hist > 0 else 0.0
        bounce_rate = (total_bounced / total_hist) * 100.0 if total_hist > 0 else 0.0
        deep_rate = (total_deep / total_hist) * 100.0 if total_hist > 0 else 0.0

        return {
            "average_reading_duration_seconds": round(avg_dur, 2),
            "completion_rate_percentage": round(comp_rate, 2),
            "average_scroll_depth_percentage": round(avg_scroll, 2),
            "bounce_rate_percentage": round(bounce_rate, 2),
            "deep_read_rate_percentage": round(deep_rate, 2),
            "total_articles_completed": total_comp,
            "total_sessions_count": total_sess,
            "total_reading_history_count": total_hist,
        }
