"""engine.py — Phase 18 Personal News Briefing Engine Main Service."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.user import User, UserProfile
from app.models.topic import Topic
from app.models.interest import UserInterest
from app.models.reading_history import ReadingHistory
from app.models.article import Article
from app.newspaper.models import NewspaperEdition
from app.editorial.candidate_selector import EditorialCandidateSelector
from app.editorial.schemas import EditorialCandidate
from app.briefings.models import (
    BriefingStatus,
    BriefingType,
    Daypart,
    NewsBriefing,
    NewsBriefingItem,
)
from app.briefings.schemas import (
    BriefingHistorySummary,
    BriefingItemResponse,
    BriefingStatusResponse,
    NewsBriefingResponse,
)
from app.briefings.session_service import NewsSessionService
from app.briefings.change_detector import ChangeDetector
from app.briefings.briefing_selector import BriefingSelector, BriefingCandidate

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class PersonalNewsBriefingEngine:
    """
    Main Service for Phase 18 Personal News Briefings.
    Provides session-aware, dynamic, and concise daypart briefings.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.session_service = NewsSessionService(session)
        self.candidate_selector = EditorialCandidateSelector(session)
        self.change_detector = ChangeDetector(session)
        self.selector = BriefingSelector(self.change_detector)

    def get_user_timezone(self, user: Optional[User]) -> ZoneInfo:
        """Resolves user's configured timezone or falls back to system default."""
        tz_name = settings.DEFAULT_TIMEZONE
        if user:
            try:
                from sqlalchemy import inspect as sa_inspect
                insp = sa_inspect(user, raise_errors=False)
                if insp and "profile" in insp.attrs:
                    profile = insp.attrs["profile"].loaded_value
                    if profile and hasattr(profile, "timezone") and profile.timezone:
                        tz_name = profile.timezone
            except Exception:
                pass
        try:
            return ZoneInfo(tz_name)
        except Exception:
            return ZoneInfo("UTC")

    def get_user_local_datetime(self, user: Optional[User]) -> datetime:
        """Returns the current datetime in the user's timezone."""
        user_tz = self.get_user_timezone(user)
        return datetime.now(user_tz)

    def get_user_today_date_str(self, user: Optional[User]) -> str:
        """Returns YYYY-MM-DD in the user's timezone."""
        return self.get_user_local_datetime(user).strftime("%Y-%m-%d")

    def detect_daypart(self, user: Optional[User]) -> Tuple[str, str]:
        """
        Determines daypart (MORNING, MIDDAY, EVENING, NIGHT) and greeting for user's local time.

        Returns:
            (daypart_str, greeting_str)
        """
        local_dt = self.get_user_local_datetime(user)
        hour = local_dt.hour

        if 5 <= hour < 12:
            return Daypart.MORNING.value, "GOOD MORNING"
        elif 12 <= hour < 17:
            return Daypart.MIDDAY.value, "GOOD AFTERNOON"
        elif 17 <= hour < 22:
            return Daypart.EVENING.value, "GOOD EVENING"
        else:
            return Daypart.NIGHT.value, "GOOD EVENING"

    async def generate_briefing(
        self,
        user_id: uuid.UUID,
        briefing_date: Optional[str] = None,
        daypart: Optional[str] = None,
        force_refresh: bool = False,
        version: Optional[int] = None,
    ) -> NewsBriefingResponse:
        """
        Generates or refreshes a personalized news briefing for the user and target date.
        """
        stmt = (
            select(User)
            .options(selectinload(User.profile), selectinload(User.interests))
            .where(User.id == user_id)
        )
        res = await self.session.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        target_date_str = briefing_date or self.get_user_today_date_str(user)
        detected_daypart, greeting = self.detect_daypart(user)
        target_daypart = daypart or detected_daypart

        # Check existing briefing
        latest_briefing = await self._get_latest_briefing_model(user_id, target_date_str)

        if latest_briefing and not force_refresh and latest_briefing.status == BriefingStatus.READY.value:
            return await self._format_briefing_response(latest_briefing, user_id, greeting)

        next_version = (latest_briefing.version + 1) if (latest_briefing and force_refresh) else (version or 1)

        try:
            # 1. Discover user's last session baseline
            last_session_at = await self.session_service.get_last_meaningful_session_time(user_id)

            # 2. Collect candidate pool
            candidates, exclusions = await self.candidate_selector.get_candidate_pool(user_id=user_id)

            # Extract user top positive topics
            user_topics: List[str] = []
            if user.interests:
                int_topic_ids = [i.topic_id for i in user.interests if i.preference_type == "POSITIVE"]
                if int_topic_ids:
                    stmt_top = select(Topic.name).where(Topic.id.in_(int_topic_ids))
                    t_res = await self.session.execute(stmt_top)
                    user_topics = list(t_res.scalars().all())

            # 3. Select briefing items
            top_items, what_changed, all_items, is_caught_up, intro = self.selector.select_briefing_items(
                candidates=candidates,
                last_session_at=last_session_at,
                user_top_topics=user_topics,
                max_items=7,
                min_items=3,
                daypart=target_daypart,
            )

            # 4. Connect to today's newspaper edition if available
            edition_stmt = (
                select(NewspaperEdition.id)
                .where(
                    NewspaperEdition.user_id == user_id,
                    NewspaperEdition.edition_date == target_date_str,
                )
                .order_by(desc(NewspaperEdition.version))
                .limit(1)
            )
            edition_res = await self.session.execute(edition_stmt)
            edition_id = edition_res.scalars().first()

            # 5. Persist NewsBriefing
            briefing = NewsBriefing(
                user_id=user_id,
                edition_id=edition_id,
                briefing_date=target_date_str,
                daypart=target_daypart,
                title="YOUR DAILY BRIEFING",
                intro=intro,
                status=BriefingStatus.READY.value,
                version=next_version,
                is_caught_up=is_caught_up,
                generated_at=utc_now(),
            )
            self.session.add(briefing)
            await self.session.flush()

            # 6. Persist NewsBriefingItem records
            for pos, b_cand in enumerate(all_items):
                item = NewsBriefingItem(
                    briefing_id=briefing.id,
                    story_id=b_cand.candidate.story_id,
                    article_id=b_cand.candidate.article_id,
                    position=pos,
                    briefing_type=b_cand.briefing_type,
                    headline=b_cand.candidate.title,
                    summary=b_cand.candidate.summary,
                    reason=b_cand.reason,
                    importance=b_cand.candidate.importance_score,
                )
                self.session.add(item)

            await self.session.commit()

            fresh = await self._get_latest_briefing_model(user_id, target_date_str)
            if fresh:
                return await self._format_briefing_response(fresh, user_id, greeting, last_session_at)
            return await self._format_briefing_response(briefing, user_id, greeting, last_session_at)

        except Exception as e:
            logger.error(f"Error generating briefing for user {user_id} on {target_date_str}: {e}", exc_info=True)
            await self.session.rollback()

            if latest_briefing and latest_briefing.status == BriefingStatus.READY.value:
                return await self._format_briefing_response(latest_briefing, user_id, greeting)

            return await self._generate_fallback_briefing(user_id, target_date_str, target_daypart, next_version, greeting)

    async def get_today_briefing(self, user: User) -> NewsBriefingResponse:
        """Retrieves or creates today's briefing for the authenticated user."""
        today_str = self.get_user_today_date_str(user)
        latest = await self._get_latest_briefing_model(user.id, today_str)
        if latest and latest.status == BriefingStatus.READY.value:
            _, greeting = self.detect_daypart(user)
            return await self._format_briefing_response(latest, user.id, greeting)
        return await self.generate_briefing(user_id=user.id, briefing_date=today_str)

    async def get_briefing_by_date(
        self, user_id: uuid.UUID, briefing_date: str, version: Optional[int] = None
    ) -> Optional[NewsBriefingResponse]:
        """Retrieves a historical briefing by date and optional version."""
        if version is not None:
            stmt = (
                select(NewsBriefing)
                .where(
                    NewsBriefing.user_id == user_id,
                    NewsBriefing.briefing_date == briefing_date,
                    NewsBriefing.version == version,
                )
            )
            res = await self.session.execute(stmt)
            briefing = res.scalars().first()
        else:
            briefing = await self._get_latest_briefing_model(user_id, briefing_date)

        if not briefing:
            return None
        return await self._format_briefing_response(briefing, user_id, "DAILY BRIEFING")

    async def get_briefing_history(
        self, user_id: uuid.UUID, limit: int = 10
    ) -> List[BriefingHistorySummary]:
        """Returns historical briefing summaries for a user."""
        stmt = (
            select(NewsBriefing)
            .where(NewsBriefing.user_id == user_id)
            .order_by(desc(NewsBriefing.briefing_date), desc(NewsBriefing.version))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        briefings = list(res.scalars().all())

        summaries: List[BriefingHistorySummary] = []
        for b in briefings:
            # Query item count
            cnt_stmt = select(func.count(NewsBriefingItem.id)).where(NewsBriefingItem.briefing_id == b.id)
            cnt = (await self.session.execute(cnt_stmt)).scalar() or 0

            summaries.append(
                BriefingHistorySummary(
                    id=b.id,
                    briefing_date=b.briefing_date,
                    daypart=b.daypart,
                    title=b.title,
                    status=b.status,
                    version=b.version,
                    total_items=cnt,
                    is_caught_up=b.is_caught_up,
                    generated_at=b.generated_at,
                )
            )
        return summaries

    async def get_briefing_status(
        self, user_id: uuid.UUID, briefing_date: str
    ) -> BriefingStatusResponse:
        """Checks status, freshness, and staleness of today's briefing."""
        latest = await self._get_latest_briefing_model(user_id, briefing_date)
        if not latest:
            return BriefingStatusResponse(
                user_id=user_id,
                briefing_date=briefing_date,
                daypart=Daypart.MORNING.value,
                status="NOT_GENERATED",
                is_stale=True,
                latest_version=0,
                staleness_reasons=["Briefing has not been generated for this date."],
            )

        gen_at = ensure_utc(latest.generated_at) or utc_now()
        age_hours = (utc_now() - gen_at).total_seconds() / 3600.0
        is_stale = age_hours > 6.0
        reasons = []
        if is_stale:
            reasons.append("Briefing is older than 6 hours.")

        return BriefingStatusResponse(
            user_id=user_id,
            briefing_date=briefing_date,
            daypart=latest.daypart,
            status=latest.status,
            is_stale=is_stale,
            latest_version=latest.version,
            staleness_reasons=reasons,
        )

    async def _get_latest_briefing_model(
        self, user_id: uuid.UUID, briefing_date: str
    ) -> Optional[NewsBriefing]:
        stmt = (
            select(NewsBriefing)
            .where(
                NewsBriefing.user_id == user_id,
                NewsBriefing.briefing_date == briefing_date,
            )
            .order_by(desc(NewsBriefing.version))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def _format_briefing_response(
        self,
        briefing: NewsBriefing,
        user_id: uuid.UUID,
        greeting: str = "GOOD MORNING",
        last_session_at: Optional[datetime] = None,
    ) -> NewsBriefingResponse:
        # Load items with eager relationships
        item_stmt = (
            select(NewsBriefingItem)
            .options(
                selectinload(NewsBriefingItem.story),
                selectinload(NewsBriefingItem.article).selectinload(Article.analysis),
                selectinload(NewsBriefingItem.article).selectinload(Article.topics),
                selectinload(NewsBriefingItem.article).selectinload(Article.source),
            )
            .where(NewsBriefingItem.briefing_id == briefing.id)
            .order_by(NewsBriefingItem.position.asc())
        )
        item_res = await self.session.execute(item_stmt)
        items = list(item_res.scalars().all())

        # Check user read states for articles in briefing
        art_ids = [it.article_id for it in items if it.article_id]
        read_set = set()
        if art_ids:
            read_stmt = select(ReadingHistory.article_id).where(
                ReadingHistory.user_id == user_id,
                ReadingHistory.article_id.in_(art_ids),
                ReadingHistory.last_completion_percentage >= 0.8,
            )
            read_res = await self.session.execute(read_stmt)
            read_set = set(read_res.scalars().all())

        item_responses: List[BriefingItemResponse] = []
        for it in items:
            art = it.article
            st = it.story
            analysis = art.analysis if art else None

            # Extract source info & independent count
            src_name = "Independent Source"
            if art and art.source:
                src_name = art.source.name
            elif st:
                src_name = "Multi-Source Story"

            src_count = st.source_count if st else 1
            indep_count = st.independent_source_count if st else 1
            topics = [t.name for t in art.topics] if (art and art.topics) else []
            if st and st.primary_topic and st.primary_topic.name not in topics:
                topics.append(st.primary_topic.name)

            pub_at = (st.first_published_at if st else (art.published_at if art else it.created_at))
            updated_at = (st.last_updated_at if st else (art.published_at if art else it.created_at))
            url = (art.canonical_url or art.source_url) if art else None
            top_image = art.image_url if art else None

            resp = BriefingItemResponse(
                id=it.id,
                briefing_id=it.briefing_id,
                story_id=it.story_id,
                article_id=it.article_id,
                position=it.position,
                briefing_type=it.briefing_type,
                headline=it.headline,
                summary=it.summary,
                reason=it.reason,
                importance=it.importance,
                primary_category=(analysis.primary_category if analysis else "GENERAL"),
                topics=topics,
                source_name=src_name,
                source_count=src_count,
                independent_source_count=indep_count,
                reading_time_minutes=(art.reading_time_minutes if art else 3),
                published_at=pub_at,
                last_updated_at=updated_at,
                url=url,
                top_image_url=top_image,
                is_read=(it.article_id in read_set if it.article_id else False),
                is_developing=(st.status == "DEVELOPING" if st else False),
                created_at=it.created_at,
            )
            item_responses.append(resp)

        top_items = item_responses[:3]
        what_changed = [
            it for it in item_responses
            if it.briefing_type in (BriefingType.UPDATED.value, BriefingType.FOLLOW_UP.value)
        ]

        return NewsBriefingResponse(
            id=briefing.id,
            user_id=briefing.user_id,
            edition_id=briefing.edition_id,
            briefing_date=briefing.briefing_date,
            daypart=briefing.daypart,
            title=briefing.title,
            greeting=greeting,
            intro=briefing.intro,
            status=briefing.status,
            version=briefing.version,
            is_caught_up=briefing.is_caught_up,
            total_items=len(item_responses),
            top_items=top_items,
            what_changed=what_changed,
            items=item_responses,
            generated_at=briefing.generated_at,
            last_session_at=last_session_at,
        )

    async def _generate_fallback_briefing(
        self,
        user_id: uuid.UUID,
        target_date_str: str,
        target_daypart: str,
        version: int,
        greeting: str,
    ) -> NewsBriefingResponse:
        """Creates a safe, minimal fallback briefing if an unexpected failure occurs."""
        logger.warning(f"Generating emergency fallback briefing for user {user_id}")
        stmt = (
            select(Article)
            .options(selectinload(Article.analysis), selectinload(Article.topics), selectinload(Article.source))
            .where(Article.status == "PUBLISHED")
            .order_by(desc(Article.published_at))
            .limit(3)
        )
        res = await self.session.execute(stmt)
        articles = list(res.scalars().all())

        briefing = NewsBriefing(
            user_id=user_id,
            briefing_date=target_date_str,
            daypart=target_daypart,
            title="YOUR DAILY BRIEFING",
            intro="Here are today's essential news highlights.",
            status=BriefingStatus.READY.value,
            version=version,
            is_caught_up=False,
            generated_at=utc_now(),
        )
        self.session.add(briefing)
        await self.session.flush()

        for idx, art in enumerate(articles):
            item = NewsBriefingItem(
                briefing_id=briefing.id,
                article_id=art.id,
                position=idx,
                briefing_type=BriefingType.IMPORTANT.value if idx == 0 else BriefingType.NEW.value,
                headline=art.title,
                summary=art.analysis.summary if art.analysis else art.description,
                reason="Essential development today.",
                importance=0.8 if idx == 0 else 0.5,
            )
            self.session.add(item)

        await self.session.commit()
        return await self._format_briefing_response(briefing, user_id, greeting)
