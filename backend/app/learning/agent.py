"""agent.py — Automatic Interest Learning Agent.

Learns user topic, entity, and keyword affinities from continuous behavioral signals
(opens, reads, likes, saves, skips, completion, not_interested) and updates the user's
composite semantic profile.
"""
import logging
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.models.topic import Topic
from app.models.article import Article
from app.models.interest import UserInterest
from app.models.entity import Entity
from app.models.analysis import ArticleAnalysis, ArticleKeyword
from app.learning.models import (
    UserBehaviorEvent,
    ReadingSession,
    UserEntityInterest,
    UserKeywordInterest,
)
from app.learning.schemas import LearnedInterestItem, UserLearningProfileResponse
from app.personalization.services.user_embedding_service import UserEmbeddingService

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InterestLearningAgent:
    """Autonomous intelligence component learning user interests from multi-factor behavioral interactions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_embedding_service = UserEmbeddingService(session)

    # -------------------------------------------------------------------------
    # Behavior Signal Resolution
    # -------------------------------------------------------------------------
    @staticmethod
    def get_behavior_weight(event_type: str, value: float = 1.0) -> float:
        """Resolve base signal weight for a given behavior event type."""
        event_upper = event_type.upper().strip()

        weights_map = {
            "ARTICLE_OPEN": settings.WEIGHT_ARTICLE_OPEN,
            "ARTICLE_READ": settings.WEIGHT_ARTICLE_READ,
            "ARTICLE_COMPLETE": settings.WEIGHT_ARTICLE_COMPLETE,
            "ARTICLE_LIKE": settings.WEIGHT_ARTICLE_LIKE,
            "ARTICLE_SAVE": settings.WEIGHT_ARTICLE_SAVE,
            "ARTICLE_SHARE": settings.WEIGHT_ARTICLE_SHARE,
            "ARTICLE_NOT_INTERESTED": settings.WEIGHT_ARTICLE_NOT_INTERESTED,
            "ARTICLE_SKIP": settings.WEIGHT_ARTICLE_SKIP,
            "ARTICLE_IMPRESSION": settings.WEIGHT_ARTICLE_IMPRESSION,
        }

        base_weight = weights_map.get(event_upper, 0.0)

        # Scale by multiplier if provided (e.g. reading dwell multiplier)
        if value > 0 and event_upper in ("ARTICLE_READ", "ARTICLE_COMPLETE"):
            multiplier = max(0.5, min(2.0, value))
            return base_weight * multiplier

        return base_weight

    # -------------------------------------------------------------------------
    # Core Event Processing Pipeline
    # -------------------------------------------------------------------------
    async def process_event(
        self,
        user_id: uuid.UUID,
        event_type: str,
        article_id: uuid.UUID,
        value: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        commit: bool = True,
    ) -> UserBehaviorEvent:
        """Record behavior event and incrementally update topic, entity, and keyword affinities."""
        now = utc_now()

        # 1. Persist behavior event log
        event = UserBehaviorEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            article_id=article_id,
            event_type=event_type.upper().strip(),
            value=value,
            event_metadata=metadata,
            created_at=now,
        )
        self.session.add(event)

        # 2. If impression only, persist event without mutating scores immediately
        if event.event_type == "ARTICLE_IMPRESSION":
            if commit:
                await self.session.commit()
            return event

        # 3. Load article with relationships
        stmt = (
            select(Article)
            .where(Article.id == article_id)
            .options(
                selectinload(Article.topics),
                selectinload(Article.entities),
                selectinload(Article.keywords),
                selectinload(Article.analysis),
            )
        )
        result = await self.session.execute(stmt)
        article = result.scalar_one_or_none()
        if not article:
            logger.warning(f"Article {article_id} not found for behavior event {event_type}")
            if commit:
                await self.session.commit()
            return event

        # 4. Resolve behavior signal
        signal = self.get_behavior_weight(event.event_type, value)

        # 5. Apply Topic Updates
        await self._apply_topic_updates(user_id, article, signal)

        # 6. Apply Entity Updates
        await self._apply_entity_updates(user_id, article, signal)

        # 7. Apply Keyword Updates
        await self._apply_keyword_updates(user_id, article, signal)

        if commit:
            await self.session.commit()
            # Invalidate cached user embedding so fresh learned interests are incorporated on next ranking
            await self.user_embedding_service.invalidate_user_embedding(user_id)

        return event

    async def process_events_batch(
        self,
        user_id: uuid.UUID,
        events: List[Dict[str, Any]],
    ) -> List[UserBehaviorEvent]:
        """Process a batch of interaction events efficiently."""
        recorded = []
        for ev in events:
            event_obj = await self.process_event(
                user_id=user_id,
                event_type=ev.get("event_type", "ARTICLE_OPEN"),
                article_id=uuid.UUID(str(ev["article_id"])),
                value=float(ev.get("value", 1.0)),
                metadata=ev.get("metadata"),
                commit=False,
            )
            recorded.append(event_obj)

        await self.session.commit()
        await self.user_embedding_service.invalidate_user_embedding(user_id)
        return recorded

    # -------------------------------------------------------------------------
    # Topic Learning
    # -------------------------------------------------------------------------
    async def _apply_topic_updates(self, user_id: uuid.UUID, article: Article, signal: float) -> None:
        """Update user topic interests based on article topics and confidence."""
        if not article.topics:
            return

        now = utc_now()
        for topic in article.topics:
            topic_conf = getattr(topic, "confidence", 1.0) or 1.0
            try:
                topic_conf = float(topic_conf)
            except (TypeError, ValueError):
                topic_conf = 1.0

            effective_signal = signal * topic_conf

            stmt = select(UserInterest).where(
                UserInterest.user_id == user_id,
                UserInterest.topic_id == topic.id,
            )
            res = await self.session.execute(stmt)
            interest = res.scalar_one_or_none()

            if interest:
                # Update existing interest
                old_score = interest.interest_score
                delta = settings.INTEREST_LEARNING_RATE * effective_signal

                if interest.preference_type == "NEGATIVE" and effective_signal < 0:
                    # Negative signal on already negative preference increases negative strength
                    new_score = min(1.0, old_score + abs(delta))
                elif interest.preference_type == "NEGATIVE" and effective_signal > 0:
                    # Positive signal on negative preference softens negative strength
                    new_score = max(0.0, old_score - delta)
                else:
                    new_score = max(0.0, min(1.0, old_score + delta))

                interest.interest_score = round(new_score, 4)

                # Confidence increases with interaction
                old_conf = getattr(interest, "confidence", 0.5) or 0.5
                interest.confidence = round(
                    min(settings.MAX_INTEREST_CONFIDENCE, old_conf + settings.CONFIDENCE_GROWTH_RATE * abs(effective_signal)),
                    4,
                )

                if interest.source in ("ONBOARDING", "USER_ACTION", "EXPLICIT"):
                    # Maintain explicit authority with hybrid marker
                    interest.source = "HYBRID"
                interest.updated_at = now
            else:
                # Create newly learned topic interest
                initial_score = max(0.0, min(1.0, 0.50 + (settings.INTEREST_LEARNING_RATE * effective_signal)))
                pref_type = "POSITIVE" if effective_signal >= 0 else "NEGATIVE"
                init_conf = round(
                    min(
                        settings.MAX_INTEREST_CONFIDENCE,
                        settings.MIN_INTEREST_CONFIDENCE + settings.CONFIDENCE_GROWTH_RATE * abs(effective_signal),
                    ),
                    4,
                )

                new_interest = UserInterest(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    topic_id=topic.id,
                    interest_score=round(initial_score, 4),
                    confidence=init_conf,
                    preference_type=pref_type,
                    source="LEARNED",
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(new_interest)

    # -------------------------------------------------------------------------
    # Entity Learning
    # -------------------------------------------------------------------------
    async def _apply_entity_updates(self, user_id: uuid.UUID, article: Article, signal: float) -> None:
        """Update user entity affinities based on extracted article entities."""
        if not article.entities:
            return

        now = utc_now()
        for entity in article.entities:
            ent_conf = getattr(entity, "confidence", 1.0) or 1.0
            try:
                ent_conf = float(ent_conf)
            except (TypeError, ValueError):
                ent_conf = 1.0

            effective_signal = signal * ent_conf

            stmt = select(UserEntityInterest).where(
                UserEntityInterest.user_id == user_id,
                UserEntityInterest.entity_id == entity.id,
            )
            res = await self.session.execute(stmt)
            entity_interest = res.scalar_one_or_none()

            if entity_interest:
                old_score = entity_interest.score
                delta = settings.INTEREST_LEARNING_RATE * effective_signal
                new_score = max(0.0, min(1.0, old_score + delta))
                entity_interest.score = round(new_score, 4)

                old_conf = entity_interest.confidence
                entity_interest.confidence = round(
                    min(settings.MAX_INTEREST_CONFIDENCE, old_conf + settings.CONFIDENCE_GROWTH_RATE * abs(effective_signal)),
                    4,
                )
                entity_interest.interaction_count += 1
                if effective_signal >= 0:
                    entity_interest.positive_count += 1
                else:
                    entity_interest.negative_count += 1
                entity_interest.updated_at = now
            else:
                initial_score = max(0.0, min(1.0, 0.50 + (settings.INTEREST_LEARNING_RATE * effective_signal)))
                init_conf = round(
                    min(
                        settings.MAX_INTEREST_CONFIDENCE,
                        settings.MIN_INTEREST_CONFIDENCE + settings.CONFIDENCE_GROWTH_RATE * abs(effective_signal),
                    ),
                    4,
                )
                new_ent_int = UserEntityInterest(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    entity_id=entity.id,
                    score=round(initial_score, 4),
                    confidence=init_conf,
                    interaction_count=1,
                    positive_count=1 if effective_signal >= 0 else 0,
                    negative_count=1 if effective_signal < 0 else 0,
                    updated_at=now,
                )
                self.session.add(new_ent_int)

    # -------------------------------------------------------------------------
    # Keyword Learning
    # -------------------------------------------------------------------------
    async def _apply_keyword_updates(self, user_id: uuid.UUID, article: Article, signal: float) -> None:
        """Update user keyword affinities based on article keywords."""
        if not article.keywords:
            return

        now = utc_now()
        for kw_item in article.keywords:
            raw_kw = getattr(kw_item, "keyword", "") or ""
            norm_kw = raw_kw.strip().lower()
            if not norm_kw or len(norm_kw) < 2:
                continue

            kw_weight = getattr(kw_item, "weight", 1.0) or 1.0
            try:
                kw_weight = float(kw_weight)
            except (TypeError, ValueError):
                kw_weight = 1.0

            effective_signal = signal * kw_weight

            stmt = select(UserKeywordInterest).where(
                UserKeywordInterest.user_id == user_id,
                UserKeywordInterest.keyword == norm_kw,
            )
            res = await self.session.execute(stmt)
            kw_interest = res.scalar_one_or_none()

            if kw_interest:
                old_score = kw_interest.score
                delta = settings.INTEREST_LEARNING_RATE * effective_signal
                new_score = max(0.0, min(1.0, old_score + delta))
                kw_interest.score = round(new_score, 4)

                old_conf = kw_interest.confidence
                kw_interest.confidence = round(
                    min(settings.MAX_INTEREST_CONFIDENCE, old_conf + settings.CONFIDENCE_GROWTH_RATE * abs(effective_signal)),
                    4,
                )
                kw_interest.interaction_count += 1
                if effective_signal >= 0:
                    kw_interest.positive_count += 1
                else:
                    kw_interest.negative_count += 1
                kw_interest.updated_at = now
            else:
                initial_score = max(0.0, min(1.0, 0.50 + (settings.INTEREST_LEARNING_RATE * effective_signal)))
                init_conf = round(
                    min(
                        settings.MAX_INTEREST_CONFIDENCE,
                        settings.MIN_INTEREST_CONFIDENCE + settings.CONFIDENCE_GROWTH_RATE * abs(effective_signal),
                    ),
                    4,
                )
                new_kw_int = UserKeywordInterest(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    keyword=norm_kw,
                    score=round(initial_score, 4),
                    confidence=init_conf,
                    interaction_count=1,
                    positive_count=1 if effective_signal >= 0 else 0,
                    negative_count=1 if effective_signal < 0 else 0,
                    updated_at=now,
                )
                self.session.add(new_kw_int)

    # -------------------------------------------------------------------------
    # Reading Sessions
    # -------------------------------------------------------------------------
    async def start_reading_session(
        self,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> ReadingSession:
        """Initiate an active reading session for an article."""
        now = utc_now()
        session_obj = ReadingSession(
            id=uuid.uuid4(),
            user_id=user_id,
            article_id=article_id,
            started_at=now,
            created_at=now,
        )
        self.session.add(session_obj)

        # Also log ARTICLE_OPEN event
        await self.process_event(
            user_id=user_id,
            event_type="ARTICLE_OPEN",
            article_id=article_id,
            value=1.0,
            commit=False,
        )

        await self.session.commit()
        await self.session.refresh(session_obj)
        return session_obj

    async def end_reading_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
        completion_percentage: Optional[float] = None,
    ) -> ReadingSession:
        """Conclude active reading session, calculate duration & completion, and trigger learning."""
        now = utc_now()

        stmt = select(ReadingSession).where(
            ReadingSession.id == session_id,
            ReadingSession.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        session_obj = res.scalar_one_or_none()

        if not session_obj:
            # Create session on the fly if not found
            session_obj = ReadingSession(
                id=session_id,
                user_id=user_id,
                article_id=article_id,
                started_at=now,
                created_at=now,
            )
            self.session.add(session_obj)

        session_obj.ended_at = now
        duration = max(0.0, (now - session_obj.started_at).total_seconds())
        session_obj.duration_seconds = round(duration, 2)

        # Estimate completion if not supplied
        if completion_percentage is not None:
            calc_comp = max(0.0, min(100.0, float(completion_percentage)))
        else:
            # Fetch article reading time
            stmt_art = select(Article).where(Article.id == article_id)
            res_art = await self.session.execute(stmt_art)
            art = res_art.scalar_one_or_none()
            expected_seconds = (art.reading_time_minutes * 60.0) if art else 180.0
            calc_comp = max(0.0, min(100.0, (duration / expected_seconds) * 100.0))

        session_obj.completion_percentage = round(calc_comp, 2)

        # Determine appropriate learning event
        if calc_comp >= 75.0 or duration >= 180.0:
            ev_type = "ARTICLE_COMPLETE"
            val = round(1.0 + min(1.0, duration / 300.0), 2)
        elif duration >= 15.0 or calc_comp >= 25.0:
            ev_type = "ARTICLE_READ"
            val = round(min(1.5, duration / 60.0), 2)
        else:
            # Quick bounce / skip
            ev_type = "ARTICLE_SKIP"
            val = 1.0

        await self.process_event(
            user_id=user_id,
            event_type=ev_type,
            article_id=article_id,
            value=val,
            metadata={
                "duration_seconds": duration,
                "completion_percentage": calc_comp,
            },
            commit=False,
        )

        await self.session.commit()
        await self.session.refresh(session_obj)
        await self.user_embedding_service.invalidate_user_embedding(user_id)
        return session_obj

    # -------------------------------------------------------------------------
    # Profile Inspection
    # -------------------------------------------------------------------------
    async def get_user_learning_profile(self, user_id: uuid.UUID) -> UserLearningProfileResponse:
        """Inspect explicit vs learned interests, entities, and keywords."""
        # 1. Topic Interests
        stmt_topic = (
            select(UserInterest)
            .options(selectinload(UserInterest.topic))
            .where(UserInterest.user_id == user_id)
        )
        res_topic = await self.session.execute(stmt_topic)
        topic_interests = res_topic.scalars().all()

        explicit_list: List[LearnedInterestItem] = []
        learned_topics: List[LearnedInterestItem] = []

        for ti in topic_interests:
            item = LearnedInterestItem(
                name=ti.topic.name,
                slug=ti.topic.slug,
                score=ti.interest_score,
                confidence=getattr(ti, "confidence", 1.0) or 1.0,
                source=ti.source,
            )
            if ti.source in ("ONBOARDING", "USER_ACTION", "EXPLICIT"):
                explicit_list.append(item)
            elif ti.source == "HYBRID":
                explicit_list.append(item)
                learned_topics.append(item)
            else:
                learned_topics.append(item)

        # 2. Entity Interests
        stmt_ent = (
            select(UserEntityInterest)
            .options(selectinload(UserEntityInterest.entity))
            .where(UserEntityInterest.user_id == user_id)
            .order_by(UserEntityInterest.score.desc())
        )
        res_ent = await self.session.execute(stmt_ent)
        entity_interests = res_ent.scalars().all()

        learned_entities = [
            LearnedInterestItem(
                name=ei.entity.name,
                slug=ei.entity.normalized_name,
                score=ei.score,
                confidence=ei.confidence,
                source="LEARNED",
                interaction_count=ei.interaction_count,
                positive_count=ei.positive_count,
                negative_count=ei.negative_count,
            )
            for ei in entity_interests
        ]

        # 3. Keyword Interests
        stmt_kw = (
            select(UserKeywordInterest)
            .where(UserKeywordInterest.user_id == user_id)
            .order_by(UserKeywordInterest.score.desc())
        )
        res_kw = await self.session.execute(stmt_kw)
        keyword_interests = res_kw.scalars().all()

        learned_keywords = [
            LearnedInterestItem(
                name=ki.keyword,
                slug=ki.keyword,
                score=ki.score,
                confidence=ki.confidence,
                source="LEARNED",
                interaction_count=ki.interaction_count,
                positive_count=ki.positive_count,
                negative_count=ki.negative_count,
            )
            for ki in keyword_interests
        ]

        # Summary text
        top_explicit = [e.name for e in explicit_list[:3]]
        top_learned = [lt.name for lt in learned_topics[:3] if lt.score >= 0.55]
        top_entities = [le.name for le in learned_entities[:3] if le.score >= 0.55]

        parts = []
        if top_explicit:
            parts.append(f"Your interests: {', '.join(top_explicit)}")
        if top_learned or top_entities:
            learned_names = top_learned + top_entities
            parts.append(f"Learning: {', '.join(learned_names[:4])}")

        summary = ". ".join(parts) if parts else "Set your interests or read articles to train your personal edition."

        return UserLearningProfileResponse(
            user_id=user_id,
            explicit_interests=explicit_list,
            learned_topics=learned_topics,
            learned_entities=learned_entities,
            learned_keywords=learned_keywords,
            summary=summary,
        )
