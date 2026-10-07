"""breaking_news.py — Phase 22 Automated Breaking News Detection & Personalized Event Engine."""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.breaking_news import BreakingNewsEvent, BreakingNewsStatus
from app.models.user import User
from app.models.user_preferences import UserNewspaperPreferences
from app.story_intelligence.models import Story

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BreakingNewsEngine:
    """Detects global breaking news developments and evaluates personalized user thresholds."""

    BREAKING_IMPORTANCE_THRESHOLD = 0.85
    RAPID_SOURCE_COUNT_THRESHOLD = 3
    USER_RELEVANCE_THRESHOLD = 0.65

    def __init__(self, session: AsyncSession):
        self.session = session

    async def detect_breaking_stories(self, lookback_hours: int = 6) -> List[BreakingNewsEvent]:
        """Scans active/developing stories for breaking event criteria."""
        now = utc_now()
        cutoff = now - timedelta(hours=lookback_hours)

        stmt = (
            select(Story)
            .options(
                selectinload(Story.primary_topic),
                selectinload(Story.primary_article),
                selectinload(Story.latest_article),
            )
            .where(
                Story.last_updated_at >= cutoff,
                Story.merged_into_story_id.is_(None),
                Story.importance_score >= self.BREAKING_IMPORTANCE_THRESHOLD,
            )
            .order_by(desc(Story.importance_score))
        )
        res = await self.session.execute(stmt)
        stories = list(res.scalars().all())

        new_events: List[BreakingNewsEvent] = []
        for s in stories:
            # Check if active event already exists for this story
            stmt_evt = select(BreakingNewsEvent).where(
                BreakingNewsEvent.story_id == s.id,
                BreakingNewsEvent.status == BreakingNewsStatus.ACTIVE,
            )
            res_evt = await self.session.execute(stmt_evt)
            existing = res_evt.scalar_one_or_none()

            if not existing:
                reason = (
                    f"High global importance ({round(s.importance_score, 2)}) with "
                    f"{s.source_count} sources monitoring live developments in {s.primary_topic.name if s.primary_topic else 'world news'}."
                )
                event = BreakingNewsEvent(
                    id=uuid.uuid4(),
                    story_id=s.id,
                    importance=s.importance_score,
                    detected_at=now,
                    status=BreakingNewsStatus.ACTIVE,
                    reason=reason,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(event)
                new_events.append(event)
                logger.info(f"Breaking news event detected for Story '{s.title}' (ID: {s.id})")

        if new_events:
            await self.session.commit()

        return new_events

    async def get_relevant_users_for_breaking_event(
        self,
        event: BreakingNewsEvent,
    ) -> List[User]:
        """Identifies users whose personalized profile exceeds the breaking news threshold."""
        stmt_story = (
            select(Story)
            .options(
                selectinload(Story.primary_topic),
                selectinload(Story.primary_article),
            )
            .where(Story.id == event.story_id)
        )
        res_story = await self.session.execute(stmt_story)
        story = res_story.scalar_one_or_none()
        if not story:
            return []

        # Query active users
        stmt_users = (
            select(User)
            .join(UserNewspaperPreferences, User.id == UserNewspaperPreferences.user_id, isouter=True)
            .where(
                User.is_active.is_(True),
                or_(
                    UserNewspaperPreferences.breaking_news_enabled.is_(True),
                    UserNewspaperPreferences.id.is_(None),  # Default is True
                ),
            )
        )
        res_users = await self.session.execute(stmt_users)
        users = list(res_users.scalars().all())

        from app.models.interest import UserInterest
        from app.learning.evidence_models import UserTopicBehaviorPreference

        relevant_users: List[User] = []
        topic_id = story.primary_topic_id

        for u in users:
            try:
                # Check user interests for story topic
                stmt_int = select(UserInterest).where(
                    UserInterest.user_id == u.id,
                    UserInterest.topic_slug == (story.primary_topic.slug if story.primary_topic else "none"),
                )
                res_int = await self.session.execute(stmt_int)
                interest = res_int.scalar_one_or_none()

                stmt_pref = select(UserTopicBehaviorPreference).where(
                    UserTopicBehaviorPreference.user_id == u.id,
                    UserTopicBehaviorPreference.topic_id == topic_id,
                )
                res_pref = await self.session.execute(stmt_pref)
                pref = res_pref.scalar_one_or_none()

                # User relevance is high if explicit interest exists, or behavior score > 0, or default broad interest
                if (interest and interest.preference_type == "POSITIVE") or (pref and pref.affinity_score > 0.3):
                    relevant_users.append(u)
                elif not interest and not pref and story.importance_score >= 0.95:
                    # Global historic event (e.g. >= 0.95) matches all users without negative preference
                    relevant_users.append(u)
            except Exception as e:
                logger.debug(f"Error evaluating user {u.id} for breaking news: {e}")
                continue

        logger.info(
            f"Breaking event {event.id} matched {len(relevant_users)}/{len(users)} users based on interest affinity."
        )
        return relevant_users

