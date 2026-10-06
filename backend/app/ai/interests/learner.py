"""learner.py — Phase 13 Dynamic User Interest Intelligence Service.

Coordinates continuous behavioral signal ingestion, batch learning cursor execution,
hierarchical topic propagation, dynamic topic discovery, decay application,
and natural language relevance explanations.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import select, delete, update, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.models.topic import Topic
from app.models.article import Article
from app.models.entity import Entity
from app.models.interest import UserInterest
from app.models.interest_profile import (
    UserInterestProfile,
    UserTopicPreference,
    InterestLearningEvent,
    UserInterestSnapshot,
)
from app.learning.models import UserEntityInterest, UserKeywordInterest
from app.ai.interests.signals import SignalManager, SignalType
from app.ai.interests.scoring import InterestScoringEngine, InterestState
from app.ai.interests.decay import InterestDecayEngine
from app.ai.interests.discovery import TopicPropagationEngine
from app.ai.interests.schemas import (
    DynamicInterestItem,
    DynamicProfileResponse,
    TopicPreferenceItem,
    EntityAffinityItem,
    RelevanceExplanationResponse,
)
from app.personalization.services.user_embedding_service import UserEmbeddingService

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InterestLearningService:
    """Master service for continuous user interest learning, profile lifecycle, and explanations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_embedding_service = UserEmbeddingService(session)

    # -------------------------------------------------------------------------
    # Signal Ingestion
    # -------------------------------------------------------------------------
    async def record_signal(
        self,
        user_id: uuid.UUID,
        signal_type: str,
        article_id: Optional[uuid.UUID] = None,
        topic_id: Optional[uuid.UUID] = None,
        entity_id: Optional[uuid.UUID] = None,
        source: Optional[str] = "READER",
        metadata: Optional[Dict[str, Any]] = None,
        multiplier: float = 1.0,
        immediate_process: bool = True,
    ) -> InterestLearningEvent:
        """Log a behavioral signal event and optionally process it immediately."""
        event = await SignalManager.log_event(
            session=self.session,
            user_id=user_id,
            signal_type=signal_type,
            article_id=article_id,
            topic_id=topic_id,
            entity_id=entity_id,
            source=source,
            metadata=metadata,
            multiplier=multiplier,
        )

        # Handle explicit topic preference immediately if signal is NOT_INTERESTED
        if signal_type.upper().strip() == SignalType.NOT_INTERESTED.value and topic_id:
            await self.set_topic_preference(
                user_id=user_id,
                topic_id=topic_id,
                preference="NEGATIVE",
                strength=1.0,
            )
        elif signal_type.upper().strip() == SignalType.EXPLICIT_INTEREST.value and topic_id:
            await self.sync_explicit_interest(user_id=user_id, topic_id=topic_id, score=0.85)

        if immediate_process:
            await self.session.commit()
            await self.process_unprocessed_events(user_id=user_id)
        else:
            await self.session.commit()

        return event

    # -------------------------------------------------------------------------
    # Explicit Interest Syncing
    # -------------------------------------------------------------------------
    async def sync_explicit_interest(
        self,
        user_id: uuid.UUID,
        topic_id: uuid.UUID,
        score: float = 0.85,
    ) -> UserInterestProfile:
        """Ensure an explicit interest profile record exists with EXPLICIT type."""
        now = utc_now()
        stmt = select(UserInterestProfile).where(
            UserInterestProfile.user_id == user_id,
            UserInterestProfile.topic_id == topic_id,
            UserInterestProfile.interest_type == "EXPLICIT",
        )
        res = await self.session.execute(stmt)
        record = res.scalar_one_or_none()

        if record:
            record.score = max(0.5, score)
            record.confidence = 1.0
            record.last_positive_at = now
            record.last_updated_at = now
        else:
            record = UserInterestProfile(
                id=uuid.uuid4(),
                user_id=user_id,
                topic_id=topic_id,
                interest_type="EXPLICIT",
                score=score,
                confidence=1.0,
                evidence_count=1,
                positive_count=1,
                negative_count=0,
                last_positive_at=now,
                last_updated_at=now,
                created_at=now,
            )
            self.session.add(record)

        # Also sync UserTopicPreference POSITIVE
        await self.set_topic_preference(
            user_id=user_id,
            topic_id=topic_id,
            preference="POSITIVE",
            strength=score,
        )

        return record

    # -------------------------------------------------------------------------
    # Batch Processing Pipeline (Learning Cursor)
    # -------------------------------------------------------------------------
    async def process_unprocessed_events(
        self,
        user_id: Optional[uuid.UUID] = None,
        batch_size: int = 200,
    ) -> int:
        """Process pending learning events in batch using cursor mechanics."""
        now = utc_now()
        query = select(InterestLearningEvent).where(
            InterestLearningEvent.processed == False
        )
        if user_id:
            query = query.where(InterestLearningEvent.user_id == user_id)

        query = query.order_by(InterestLearningEvent.created_at.asc()).limit(batch_size)
        res = await self.session.execute(query)
        events = res.scalars().all()

        if not events:
            return 0

        # Group events by user_id
        user_events: Dict[uuid.UUID, List[InterestLearningEvent]] = {}
        for ev in events:
            user_events.setdefault(ev.user_id, []).append(ev)

        total_processed = 0

        for uid, ev_list in user_events.items():
            await self._process_user_events_batch(uid, ev_list, now)
            total_processed += len(ev_list)

        await self.session.commit()
        return total_processed

    async def _process_user_events_batch(
        self,
        user_id: uuid.UUID,
        events: List[InterestLearningEvent],
        now: datetime,
    ) -> None:
        """Aggregate behavioral evidence and update user's dynamic profile."""
        # 1. Collect article IDs to prefetch topics, entities, keywords
        article_ids = [ev.article_id for ev in events if ev.article_id is not None]
        articles_map: Dict[uuid.UUID, Article] = {}

        if article_ids:
            stmt = (
                select(Article)
                .where(Article.id.in_(article_ids))
                .options(
                    selectinload(Article.topics),
                    selectinload(Article.entities),
                    selectinload(Article.keywords),
                )
            )
            res = await self.session.execute(stmt)
            for art in res.scalars().all():
                articles_map[art.id] = art

        # 2. Accumulate topic, entity, and keyword signals
        topic_deltas: Dict[uuid.UUID, float] = {}
        topic_pos_counts: Dict[uuid.UUID, int] = {}
        topic_neg_counts: Dict[uuid.UUID, int] = {}
        entity_deltas: Dict[uuid.UUID, float] = {}
        keyword_deltas: Dict[str, float] = {}

        for ev in events:
            weight = ev.signal_strength

            # If event specifies direct topic_id
            if ev.topic_id:
                topic_deltas[ev.topic_id] = topic_deltas.get(ev.topic_id, 0.0) + weight
                if weight > 0:
                    topic_pos_counts[ev.topic_id] = topic_pos_counts.get(ev.topic_id, 0) + 1
                elif weight < 0:
                    topic_neg_counts[ev.topic_id] = topic_neg_counts.get(ev.topic_id, 0) + 1

            # If event specifies direct entity_id
            if ev.entity_id:
                entity_deltas[ev.entity_id] = entity_deltas.get(ev.entity_id, 0.0) + weight

            # Extract from attached article
            if ev.article_id and ev.article_id in articles_map:
                art = articles_map[ev.article_id]
                for top in art.topics:
                    conf = getattr(top, "confidence", 1.0) or 1.0
                    try:
                        conf = float(conf)
                    except (TypeError, ValueError):
                        conf = 1.0
                    eff_sig = weight * conf
                    topic_deltas[top.id] = topic_deltas.get(top.id, 0.0) + eff_sig
                    if eff_sig > 0:
                        topic_pos_counts[top.id] = topic_pos_counts.get(top.id, 0) + 1
                    elif eff_sig < 0:
                        topic_neg_counts[top.id] = topic_neg_counts.get(top.id, 0) + 1

                for ent in art.entities:
                    conf = getattr(ent, "confidence", 1.0) or 1.0
                    try:
                        conf = float(conf)
                    except (TypeError, ValueError):
                        conf = 1.0
                    entity_deltas[ent.id] = entity_deltas.get(ent.id, 0.0) + (weight * conf)

                for kw in art.keywords:
                    raw_kw = (kw.keyword or "").strip().lower()
                    if raw_kw and len(raw_kw) >= 2:
                        w = getattr(kw, "weight", 1.0) or 1.0
                        try:
                            w = float(w)
                        except (TypeError, ValueError):
                            w = 1.0
                        keyword_deltas[raw_kw] = keyword_deltas.get(raw_kw, 0.0) + (weight * w)

            # Mark event processed
            ev.processed = True
            ev.processed_at = now

        # 3. Apply Topic Updates & Hierarchical Propagation
        await self._apply_aggregated_topic_updates(
            user_id=user_id,
            topic_deltas=topic_deltas,
            topic_pos_counts=topic_pos_counts,
            topic_neg_counts=topic_neg_counts,
            now=now,
        )

        # 4. Apply Entity Updates
        await self._apply_aggregated_entity_updates(user_id=user_id, entity_deltas=entity_deltas, now=now)

        # 5. Apply Keyword Updates
        await self._apply_aggregated_keyword_updates(user_id=user_id, keyword_deltas=keyword_deltas, now=now)

        # 6. Apply Time Decay to all learned/inferred interests
        await self.apply_interest_decay(user_id=user_id, now=now)

        # 7. Generate point-in-time Snapshot
        await self.generate_interest_snapshot(user_id=user_id, now=now)

        # 8. Invalidate embedding cache
        await self.user_embedding_service.invalidate_user_embedding(user_id)

    async def _apply_aggregated_topic_updates(
        self,
        user_id: uuid.UUID,
        topic_deltas: Dict[uuid.UUID, float],
        topic_pos_counts: Dict[uuid.UUID, int],
        topic_neg_counts: Dict[uuid.UUID, int],
        now: datetime,
    ) -> None:
        """Update UserInterestProfile for topics, including hierarchical ancestor propagation."""
        for tid, delta in topic_deltas.items():
            pos_c = topic_pos_counts.get(tid, 0)
            neg_c = topic_neg_counts.get(tid, 0)

            # Check if explicit preference exists
            stmt_pref = select(UserTopicPreference).where(
                UserTopicPreference.user_id == user_id,
                UserTopicPreference.topic_id == tid,
            )
            res_pref = await self.session.execute(stmt_pref)
            pref_obj = res_pref.scalar_one_or_none()
            is_neg = pref_obj.preference == "NEGATIVE" if pref_obj else False

            # Fetch or create UserInterestProfile
            stmt_prof = select(UserInterestProfile).where(
                UserInterestProfile.user_id == user_id,
                UserInterestProfile.topic_id == tid,
            )
            res_prof = await self.session.execute(stmt_prof)
            profiles = res_prof.scalars().all()

            explicit_prof = next((p for p in profiles if p.interest_type == "EXPLICIT"), None)
            learned_prof = next((p for p in profiles if p.interest_type == "LEARNED"), None)
            inferred_prof = next((p for p in profiles if p.interest_type == "INFERRED"), None)

            if explicit_prof:
                # Update explicit profile stats without eroding base explicit confidence
                explicit_prof.evidence_count += (pos_c + neg_c)
                explicit_prof.positive_count += pos_c
                explicit_prof.negative_count += neg_c
                explicit_prof.score = InterestScoringEngine.update_score(
                    explicit_prof.score, delta, is_negative_pref=is_neg
                )
                if pos_c > 0:
                    explicit_prof.last_positive_at = now
                if neg_c > 0:
                    explicit_prof.last_negative_at = now
                explicit_prof.last_updated_at = now

            elif learned_prof:
                # Update existing learned profile
                learned_prof.evidence_count += (pos_c + neg_c)
                learned_prof.positive_count += pos_c
                learned_prof.negative_count += neg_c
                learned_prof.score = InterestScoringEngine.update_score(
                    learned_prof.score, delta, is_negative_pref=is_neg
                )
                learned_prof.confidence = InterestScoringEngine.calculate_confidence(
                    learned_prof.evidence_count
                )
                if pos_c > 0:
                    learned_prof.last_positive_at = now
                if neg_c > 0:
                    learned_prof.last_negative_at = now
                learned_prof.last_updated_at = now

            elif inferred_prof:
                # Check for promotion to learned interest
                inferred_prof.evidence_count += (pos_c + neg_c)
                inferred_prof.positive_count += pos_c
                inferred_prof.negative_count += neg_c
                inferred_prof.score = InterestScoringEngine.update_score(
                    inferred_prof.score, delta, is_negative_pref=is_neg
                )
                inferred_prof.confidence = InterestScoringEngine.calculate_confidence(
                    inferred_prof.evidence_count
                )
                if pos_c > 0:
                    inferred_prof.last_positive_at = now
                if neg_c > 0:
                    inferred_prof.last_negative_at = now
                inferred_prof.last_updated_at = now

                if TopicPropagationEngine.should_promote_inferred_topic(
                    inferred_prof.evidence_count, inferred_prof.positive_count
                ):
                    inferred_prof.interest_type = "LEARNED"

            else:
                # Create newly learned or inferred profile
                init_score = InterestScoringEngine.update_score(0.50, delta, is_negative_pref=is_neg)
                init_conf = InterestScoringEngine.calculate_confidence(pos_c + neg_c)
                int_type = "LEARNED" if (pos_c + neg_c) >= 2 else "INFERRED"

                new_prof = UserInterestProfile(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    topic_id=tid,
                    interest_type=int_type,
                    score=init_score,
                    confidence=init_conf,
                    evidence_count=max(1, pos_c + neg_c),
                    positive_count=pos_c,
                    negative_count=neg_c,
                    last_positive_at=now if pos_c > 0 else None,
                    last_negative_at=now if neg_c > 0 else None,
                    last_updated_at=now,
                    created_at=now,
                )
                self.session.add(new_prof)

            # Hierarchical propagation to parent & grandparent topics
            if delta > 0:
                ancestors = await TopicPropagationEngine.get_ancestor_topics(self.session, tid)
                for anc_topic, weight_factor in ancestors:
                    anc_delta = delta * weight_factor
                    await self._propagate_to_ancestor(user_id, anc_topic.id, anc_delta, now)

    async def _propagate_to_ancestor(
        self,
        user_id: uuid.UUID,
        ancestor_topic_id: uuid.UUID,
        delta: float,
        now: datetime,
    ) -> None:
        """Propagate decayed score bonus to parent/grandparent topics."""
        stmt = select(UserInterestProfile).where(
            UserInterestProfile.user_id == user_id,
            UserInterestProfile.topic_id == ancestor_topic_id,
        )
        res = await self.session.execute(stmt)
        profiles = res.scalars().all()

        target_prof = next((p for p in profiles if p.interest_type in ("EXPLICIT", "LEARNED")), None)
        if target_prof:
            target_prof.score = InterestScoringEngine.update_score(target_prof.score, delta)
            target_prof.evidence_count += 1
            target_prof.positive_count += 1
            target_prof.last_positive_at = now
            target_prof.last_updated_at = now
        else:
            # Create inferred ancestor profile
            init_score = InterestScoringEngine.update_score(0.40, delta)
            new_anc = UserInterestProfile(
                id=uuid.uuid4(),
                user_id=user_id,
                topic_id=ancestor_topic_id,
                interest_type="INFERRED",
                score=init_score,
                confidence=0.25,
                evidence_count=1,
                positive_count=1,
                negative_count=0,
                last_positive_at=now,
                last_updated_at=now,
                created_at=now,
            )
            self.session.add(new_anc)

    async def _apply_aggregated_entity_updates(
        self,
        user_id: uuid.UUID,
        entity_deltas: Dict[uuid.UUID, float],
        now: datetime,
    ) -> None:
        """Update UserEntityInterest affinities."""
        for eid, delta in entity_deltas.items():
            stmt = select(UserEntityInterest).where(
                UserEntityInterest.user_id == user_id,
                UserEntityInterest.entity_id == eid,
            )
            res = await self.session.execute(stmt)
            record = res.scalar_one_or_none()

            if record:
                record.score = InterestScoringEngine.update_score(record.score, delta)
                record.interaction_count += 1
                if delta >= 0:
                    record.positive_count += 1
                else:
                    record.negative_count += 1
                record.confidence = InterestScoringEngine.calculate_confidence(record.interaction_count)
                record.updated_at = now
            else:
                init_score = InterestScoringEngine.update_score(0.50, delta)
                new_ent = UserEntityInterest(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    entity_id=eid,
                    score=init_score,
                    confidence=0.20,
                    interaction_count=1,
                    positive_count=1 if delta >= 0 else 0,
                    negative_count=1 if delta < 0 else 0,
                    updated_at=now,
                )
                self.session.add(new_ent)

    async def _apply_aggregated_keyword_updates(
        self,
        user_id: uuid.UUID,
        keyword_deltas: Dict[str, float],
        now: datetime,
    ) -> None:
        """Update UserKeywordInterest affinities."""
        for kw, delta in keyword_deltas.items():
            stmt = select(UserKeywordInterest).where(
                UserKeywordInterest.user_id == user_id,
                UserKeywordInterest.keyword == kw,
            )
            res = await self.session.execute(stmt)
            record = res.scalar_one_or_none()

            if record:
                record.score = InterestScoringEngine.update_score(record.score, delta)
                record.interaction_count += 1
                if delta >= 0:
                    record.positive_count += 1
                else:
                    record.negative_count += 1
                record.confidence = InterestScoringEngine.calculate_confidence(record.interaction_count)
                record.updated_at = now
            else:
                init_score = InterestScoringEngine.update_score(0.50, delta)
                new_kw = UserKeywordInterest(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    keyword=kw,
                    score=init_score,
                    confidence=0.20,
                    interaction_count=1,
                    positive_count=1 if delta >= 0 else 0,
                    negative_count=1 if delta < 0 else 0,
                    updated_at=now,
                )
                self.session.add(new_kw)

    # -------------------------------------------------------------------------
    # Time Decay Engine
    # -------------------------------------------------------------------------
    async def apply_interest_decay(
        self,
        user_id: uuid.UUID,
        half_life_days: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> None:
        """Apply exponential time decay to user's learned and inferred profiles."""
        eval_now = now or utc_now()
        stmt = select(UserInterestProfile).where(
            UserInterestProfile.user_id == user_id,
            UserInterestProfile.interest_type.in_(("LEARNED", "INFERRED")),
        )
        res = await self.session.execute(stmt)
        profiles = res.scalars().all()

        for prof in profiles:
            if prof.last_positive_at:
                decayed = InterestDecayEngine.calculate_decay(
                    current_score=prof.score,
                    last_positive_at=prof.last_positive_at,
                    interest_type=prof.interest_type,
                    half_life_days=half_life_days,
                    now=eval_now,
                )
                prof.score = decayed
                prof.last_updated_at = eval_now

    # -------------------------------------------------------------------------
    # Topic Preferences & Avoidance
    # -------------------------------------------------------------------------
    async def set_topic_preference(
        self,
        user_id: uuid.UUID,
        topic_id: uuid.UUID,
        preference: str,
        strength: float = 1.0,
    ) -> UserTopicPreference:
        """Set positive/negative/neutral preference for a topic."""
        now = utc_now()
        norm_pref = preference.upper().strip()

        stmt = select(UserTopicPreference).where(
            UserTopicPreference.user_id == user_id,
            UserTopicPreference.topic_id == topic_id,
        )
        res = await self.session.execute(stmt)
        pref_obj = res.scalar_one_or_none()

        if pref_obj:
            pref_obj.preference = norm_pref
            pref_obj.strength = strength
            pref_obj.last_updated_at = now
        else:
            pref_obj = UserTopicPreference(
                id=uuid.uuid4(),
                user_id=user_id,
                topic_id=topic_id,
                preference=norm_pref,
                strength=strength,
                confidence=1.0,
                created_at=now,
                last_updated_at=now,
            )
            self.session.add(pref_obj)

        await self.session.commit()
        return pref_obj

    # -------------------------------------------------------------------------
    # Profile Reset (Preserving Explicit Interests)
    # -------------------------------------------------------------------------
    async def reset_learned_profile(self, user_id: uuid.UUID) -> int:
        """Reset all learned and inferred interests, entity affinities, and cached vectors while preserving explicit interests."""
        # 1. Count preserved explicit interests
        stmt_count = select(func.count(UserInterestProfile.id)).where(
            UserInterestProfile.user_id == user_id,
            UserInterestProfile.interest_type == "EXPLICIT",
        )
        res_count = await self.session.execute(stmt_count)
        preserved_count = res_count.scalar() or 0

        # 2. Delete non-explicit interest profiles
        stmt_del_prof = delete(UserInterestProfile).where(
            UserInterestProfile.user_id == user_id,
            UserInterestProfile.interest_type.in_(("LEARNED", "INFERRED")),
        )
        await self.session.execute(stmt_del_prof)

        # 3. Delete learned entity interests
        stmt_del_ent = delete(UserEntityInterest).where(
            UserEntityInterest.user_id == user_id
        )
        await self.session.execute(stmt_del_ent)

        # 4. Delete learned keyword interests
        stmt_del_kw = delete(UserKeywordInterest).where(
            UserKeywordInterest.user_id == user_id
        )
        await self.session.execute(stmt_del_kw)

        # 5. Reset cached embeddings
        await self.user_embedding_service.invalidate_user_embedding(user_id)

        await self.session.commit()
        return preserved_count

    async def remove_learned_interest(self, user_id: uuid.UUID, topic_id: uuid.UUID) -> bool:
        """Remove a specific learned or inferred interest."""
        stmt = delete(UserInterestProfile).where(
            UserInterestProfile.user_id == user_id,
            UserInterestProfile.topic_id == topic_id,
            UserInterestProfile.interest_type.in_(("LEARNED", "INFERRED")),
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        await self.user_embedding_service.invalidate_user_embedding(user_id)
        return (res.rowcount or 0) > 0

    # -------------------------------------------------------------------------
    # Snapshot Generation
    # -------------------------------------------------------------------------
    async def generate_interest_snapshot(
        self,
        user_id: uuid.UUID,
        now: Optional[datetime] = None,
    ) -> UserInterestSnapshot:
        """Create a point-in-time snapshot of user's active interest profile."""
        eval_now = now or utc_now()

        # Fetch top topics
        stmt_top = (
            select(UserInterestProfile)
            .where(UserInterestProfile.user_id == user_id)
            .options(selectinload(UserInterestProfile.topic))
            .order_by(UserInterestProfile.score.desc())
            .limit(10)
        )
        res_top = await self.session.execute(stmt_top)
        top_topics = [
            {
                "topic_id": str(p.topic_id),
                "name": p.topic.name,
                "score": p.score,
                "type": p.interest_type,
            }
            for p in res_top.scalars().all()
            if p.topic
        ]

        # Fetch top entities
        stmt_ent = (
            select(UserEntityInterest)
            .where(UserEntityInterest.user_id == user_id)
            .options(selectinload(UserEntityInterest.entity))
            .order_by(UserEntityInterest.score.desc())
            .limit(10)
        )
        res_ent = await self.session.execute(stmt_ent)
        top_entities = [
            {
                "entity_id": str(e.entity_id),
                "name": e.entity.name,
                "score": e.score,
            }
            for e in res_ent.scalars().all()
            if e.entity
        ]

        snapshot = UserInterestSnapshot(
            id=uuid.uuid4(),
            user_id=user_id,
            generated_at=eval_now,
            top_topics=top_topics,
            top_entities=top_entities,
            interest_embedding_version=settings.ANALYSIS_VERSION,
        )
        self.session.add(snapshot)
        return snapshot

    # -------------------------------------------------------------------------
    # Profile Inspection & Dynamic Dashboard
    # -------------------------------------------------------------------------
    async def get_dynamic_profile(self, user_id: uuid.UUID) -> DynamicProfileResponse:
        """Fetch full dynamic interest profile categorized by state and preference."""
        # 1. Fetch all UserInterestProfile records
        stmt = (
            select(UserInterestProfile)
            .where(UserInterestProfile.user_id == user_id)
            .options(
                selectinload(UserInterestProfile.topic).selectinload(Topic.parent_topic)
            )
            .order_by(UserInterestProfile.score.desc())
        )
        res = await self.session.execute(stmt)
        profiles = res.scalars().all()

        explicit_list: List[DynamicInterestItem] = []
        strong_list: List[DynamicInterestItem] = []
        emerging_list: List[DynamicInterestItem] = []
        stable_list: List[DynamicInterestItem] = []
        declining_list: List[DynamicInterestItem] = []
        dormant_list: List[DynamicInterestItem] = []

        for p in profiles:
            if not p.topic:
                continue
            state = InterestScoringEngine.classify_state(
                score=p.score,
                confidence=p.confidence,
                evidence_count=p.evidence_count,
                positive_count=p.positive_count,
                negative_count=p.negative_count,
                last_positive_at=p.last_positive_at,
                interest_type=p.interest_type,
            )

            parent_name = p.topic.parent_topic.name if p.topic.parent_topic else None
            item = DynamicInterestItem(
                topic_id=p.topic_id,
                name=p.topic.name,
                slug=p.topic.slug,
                score=p.score,
                confidence=p.confidence,
                interest_type=p.interest_type,
                state=state.value,
                evidence_count=p.evidence_count,
                positive_count=p.positive_count,
                negative_count=p.negative_count,
                last_positive_at=p.last_positive_at,
                parent_topic_name=parent_name,
            )

            if p.interest_type == "EXPLICIT":
                explicit_list.append(item)
            elif state == InterestState.STRONG:
                strong_list.append(item)
            elif state == InterestState.EMERGING:
                emerging_list.append(item)
            elif state == InterestState.DECLINING:
                declining_list.append(item)
            elif state == InterestState.DORMANT:
                dormant_list.append(item)
            else:
                stable_list.append(item)

        # 2. Fetch Avoided Topics
        stmt_neg = (
            select(UserTopicPreference)
            .where(
                UserTopicPreference.user_id == user_id,
                UserTopicPreference.preference == "NEGATIVE",
            )
            .options(selectinload(UserTopicPreference.topic))
        )
        res_neg = await self.session.execute(stmt_neg)
        avoided = [
            TopicPreferenceItem(
                topic_id=p.topic_id,
                name=p.topic.name,
                slug=p.topic.slug,
                preference=p.preference,
                strength=p.strength,
                confidence=p.confidence,
            )
            for p in res_neg.scalars().all()
            if p.topic
        ]

        # 3. Fetch Top Entities
        stmt_ent = (
            select(UserEntityInterest)
            .where(UserEntityInterest.user_id == user_id)
            .options(selectinload(UserEntityInterest.entity))
            .order_by(UserEntityInterest.score.desc())
            .limit(10)
        )
        res_ent = await self.session.execute(stmt_ent)
        top_entities = [
            EntityAffinityItem(
                entity_id=e.entity_id,
                name=e.entity.name,
                score=e.score,
                confidence=e.confidence,
                evidence_count=e.interaction_count,
            )
            for e in res_ent.scalars().all()
            if e.entity
        ]

        # Construct summary
        summary_parts = []
        if explicit_list:
            top_exp = [i.name for i in explicit_list[:3]]
            summary_parts.append(f"Explicit: {', '.join(top_exp)}")
        if strong_list:
            top_str = [i.name for i in strong_list[:3]]
            summary_parts.append(f"Strong: {', '.join(top_str)}")
        if emerging_list:
            top_emg = [i.name for i in emerging_list[:3]]
            summary_parts.append(f"Emerging: {', '.join(top_emg)}")

        summary = ". ".join(summary_parts) if summary_parts else "Read stories to cultivate your personalized edition."

        return DynamicProfileResponse(
            user_id=user_id,
            explicit_interests=explicit_list,
            strong_interests=strong_list,
            emerging_interests=emerging_interests_list if (emerging_interests_list := emerging_list) else [],
            stable_interests=stable_list,
            declining_interests=declining_list,
            dormant_interests=dormant_list,
            avoided_topics=avoided,
            top_entities=top_entities,
            summary=summary,
        )

    # -------------------------------------------------------------------------
    # Relevance Explanation
    # -------------------------------------------------------------------------
    async def explain_article_relevance(
        self,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> RelevanceExplanationResponse:
        """Produce clear, human-understandable explanation for why an article was curated for the user."""
        # 1. Load article with topics and entities
        stmt = (
            select(Article)
            .where(Article.id == article_id)
            .options(
                selectinload(Article.topics),
                selectinload(Article.entities),
            )
        )
        res = await self.session.execute(stmt)
        article = res.scalar_one_or_none()
        if not article:
            return RelevanceExplanationResponse(
                article_id=article_id,
                article_title="Unknown Article",
                explanation="Article not found.",
                primary_factors=[],
                match_score=0.5,
            )

        # 2. Fetch user interests matching article topics
        art_topic_ids = [t.id for t in article.topics]
        stmt_prof = select(UserInterestProfile).where(
            UserInterestProfile.user_id == user_id,
            UserInterestProfile.topic_id.in_(art_topic_ids),
        ).options(selectinload(UserInterestProfile.topic))
        res_prof = await self.session.execute(stmt_prof)
        matching_profiles = res_prof.scalars().all()

        # 3. Fetch matching entities
        art_ent_ids = [e.id for e in article.entities]
        stmt_ent = select(UserEntityInterest).where(
            UserEntityInterest.user_id == user_id,
            UserEntityInterest.entity_id.in_(art_ent_ids),
        ).options(selectinload(UserEntityInterest.entity))
        res_ent = await self.session.execute(stmt_ent)
        matching_entities = res_ent.scalars().all()

        reasons = []
        factors = []
        top_score = 0.5

        for prof in matching_profiles:
            tname = prof.topic.name if prof.topic else "this topic"
            if prof.interest_type == "EXPLICIT":
                reasons.append(f"Because you explicitly selected {tname} in your preferences.")
                factors.append(f"Explicit: {tname}")
            elif prof.score >= settings.INTEREST_STRONG_THRESHOLD:
                reasons.append(f"Because you've been reading {tname} stories frequently.")
                factors.append(f"Frequent: {tname}")
            elif prof.interest_type == "INFERRED":
                reasons.append(f"Because you recently started exploring topics related to {tname}.")
                factors.append(f"Related: {tname}")
            else:
                reasons.append(f"Because you showed interest in {tname}.")
                factors.append(f"Topic: {tname}")
            top_score = max(top_score, prof.score)

        for ent in matching_entities:
            ename = ent.entity.name if ent.entity else "this subject"
            if ent.score >= 0.60:
                reasons.append(f"Because you regularly follow stories about {ename}.")
                factors.append(f"Entity: {ename}")

        if not reasons:
            explanation = "Curated based on today's top editorial stories and high general relevance."
            factors.append("Editorial Relevance")
        else:
            explanation = " ".join(reasons[:2])

        return RelevanceExplanationResponse(
            article_id=article_id,
            article_title=article.title,
            explanation=explanation,
            primary_factors=factors,
            match_score=round(top_score, 4),
        )
