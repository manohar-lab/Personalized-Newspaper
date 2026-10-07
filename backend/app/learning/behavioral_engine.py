"""behavioral_engine.py — Phase 19 Advanced User Behavioral Learning Engine.

Orchestrates multi-layer behavioral learning:
- Granular evidence capture with accidental click protection
- Evidence diversity discounting (stories vs articles)
- Short-term (7-day) vs Long-term (45-day) decay models
- Confidence scaling and contradiction penalty
- Explicit user override enforcement
- Anti-collapse distribution smoothing and discovery preservation
- Full deterministic profile rebuild from evidence history
"""
import logging
import math
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.user import User
from app.models.topic import Topic
from app.models.article import Article
from app.models.entity import Entity
from app.models.interest import UserInterest
from app.models.interest_profile import UserTopicPreference
from app.models.reading_history import ReadingHistory
from app.source_intelligence.models import UserSourceAffinity
from app.story_intelligence.models import Story
from app.learning.evidence_models import (
    UserInterestEvidence,
    UserTopicBehaviorPreference,
    UserEntityBehaviorPreference,
    UserKeywordBehaviorPreference,
    UserStoryInterestSignal,
)
from app.learning.evidence_schemas import (
    EntityInterestItem,
    KeywordInterestItem,
    ProfileRebuildResponse,
    RecordEvidenceRequest,
    StoryAffinityItem,
    TopicInterestItem,
    TopicOverrideRequest,
    UserProfileInterestsResponse,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BehavioralLearningEngine:
    """
    Advanced Behavioral Learning Engine combining Explicit, Behavioral,
    Semantic, Entity, and Source affinities into a unified user preference profile.
    """

    # Configurable Half-Lives (Days)
    SHORT_TERM_HALF_LIFE_DAYS = 7.0
    LONG_TERM_HALF_LIFE_DAYS = 45.0
    STORY_AFFINITY_EXPIRY_HOURS = 48.0

    # Configurable Signal Weights
    BASE_SIGNAL_WEIGHTS: Dict[str, float] = {
        "EXPLICIT_INTEREST": 1.00,
        "NOT_INTERESTED": -1.00,
        "SAVE": 0.85,
        "LIKE": 0.80,
        "COMPLETE": 0.75,
        "READ": 0.50,
        "SEARCH": 0.65,
        "STORY_OPEN": 0.60,
        "STORY_FOLLOW_UP": 0.65,
        "DISCOVERY_CLICK": 0.55,
        "CLICK": 0.35,
        "OPEN": 0.20,
        "SKIP": -0.15,
        "IMPRESSION": 0.02,
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # 1. Evidence Recording & Signal Ingestion
    # =========================================================================
    async def record_evidence(
        self,
        user_id: uuid.UUID,
        signal_type: str,
        target_type: str,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        dwell_time_seconds: Optional[float] = None,
        completion_ratio: Optional[float] = None,
        source_article_id: Optional[uuid.UUID] = None,
        source_story_id: Optional[uuid.UUID] = None,
        event_metadata: Optional[Dict[str, Any]] = None,
        commit: bool = True,
    ) -> UserInterestEvidence:
        """
        Records a granular behavioral evidence record with accidental click protection.
        """
        sig_upper = signal_type.upper().strip()
        target_upper = target_type.upper().strip()
        now = utc_now()

        # 1. Base Weight
        base_strength = self.BASE_SIGNAL_WEIGHTS.get(sig_upper, 0.20)

        # Check if user has paused automatic learning
        from app.models.personalization_settings import UserPersonalizationSettings
        stmt_set = select(UserPersonalizationSettings.learning_enabled).where(
            UserPersonalizationSettings.user_id == user_id
        )
        res_set = await self.session.execute(stmt_set)
        learning_flag = res_set.scalar_one_or_none()
        if learning_flag is False and sig_upper not in ("EXPLICIT_INTEREST", "NOT_INTERESTED"):
            # When learning is paused, behavioral passive signals do not alter inferred profile
            base_strength = 0.0

        # 2. Accidental Click Protection
        # If open duration < 5 seconds and completion < 5%, mark accidental with near-zero strength
        is_accidental = False
        if sig_upper in ("OPEN", "CLICK") and dwell_time_seconds is not None:
            if dwell_time_seconds < 5.0 and (completion_ratio or 0.0) < 0.05:
                is_accidental = True
                base_strength = 0.01

        # 3. Dwell Time & Completion Ratio Scaling
        computed_strength = base_strength
        if not is_accidental:
            if completion_ratio is not None and sig_upper in ("READ", "COMPLETE"):
                # Ratio capped between 0.2 and 1.3
                capped_ratio = max(0.2, min(1.3, completion_ratio))
                computed_strength = base_strength * capped_ratio
            elif dwell_time_seconds is not None and sig_upper == "READ":
                # Cap dwell multiplier
                dwell_mult = min(1.5, max(0.2, dwell_time_seconds / 180.0))
                computed_strength = base_strength * dwell_mult

        evidence = UserInterestEvidence(
            user_id=user_id,
            signal_type=sig_upper,
            target_type=target_upper,
            target_id=str(target_id) if target_id else None,
            target_name=target_name,
            strength=computed_strength,
            dwell_time_seconds=dwell_time_seconds,
            completion_ratio=completion_ratio,
            source_article_id=source_article_id,
            source_story_id=source_story_id,
            is_accidental=is_accidental,
            processed=False,
            event_metadata=event_metadata,
            created_at=now,
        )
        self.session.add(evidence)

        if commit:
            await self.session.commit()
            await self.session.refresh(evidence)

        return evidence

    async def ingest_article_interaction(
        self,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
        action_type: str,
        dwell_time_seconds: Optional[float] = None,
        completion_ratio: Optional[float] = None,
        scroll_percentage: Optional[float] = None,
        search_query: Optional[str] = None,
    ) -> List[UserInterestEvidence]:
        """
        Dissects an article interaction into multi-entity, topic, source, and keyword evidence items.
        """
        stmt = (
            select(Article)
            .options(
                selectinload(Article.topics),
                selectinload(Article.entities),
                selectinload(Article.analysis),
                selectinload(Article.source),
            )
            .where(Article.id == article_id)
        )
        res = await self.session.execute(stmt)
        article = res.scalars().first()
        if not article:
            return []

        # Find associated story if any
        story_id = None
        story_stmt = select(Story.id).join(Story.story_articles).where(Story.primary_article_id == article_id)
        s_res = await self.session.execute(story_stmt)
        story_id = s_res.scalars().first()

        evidence_list: List[UserInterestEvidence] = []
        action_upper = action_type.upper().strip()

        # 1. Topic Evidence
        if article.topics:
            for t in article.topics:
                ev = await self.record_evidence(
                    user_id=user_id,
                    signal_type=action_upper,
                    target_type="TOPIC",
                    target_id=str(t.id),
                    target_name=t.name,
                    dwell_time_seconds=dwell_time_seconds,
                    completion_ratio=completion_ratio,
                    source_article_id=article.id,
                    source_story_id=story_id,
                    commit=False,
                )
                evidence_list.append(ev)

        # 2. Entity Evidence
        if article.entities:
            for ent in article.entities[:5]:  # Top 5 entities
                ev = await self.record_evidence(
                    user_id=user_id,
                    signal_type=action_upper,
                    target_type="ENTITY",
                    target_id=str(ent.id),
                    target_name=ent.name,
                    dwell_time_seconds=dwell_time_seconds,
                    completion_ratio=completion_ratio,
                    source_article_id=article.id,
                    source_story_id=story_id,
                    commit=False,
                )
                evidence_list.append(ev)

        # 3. Source Evidence (Phase 15 Source Affinity update)
        if article.source_id:
            ev = await self.record_evidence(
                user_id=user_id,
                signal_type=action_upper,
                target_type="SOURCE",
                target_id=str(article.source_id),
                target_name=article.source.name if article.source else "News Source",
                dwell_time_seconds=dwell_time_seconds,
                completion_ratio=completion_ratio,
                source_article_id=article.id,
                source_story_id=story_id,
                commit=False,
            )
            evidence_list.append(ev)

        # 4. Story Affinity Evidence
        if story_id and action_upper in ("READ", "COMPLETE", "SAVE", "LIKE", "STORY_FOLLOW_UP"):
            ev = await self.record_evidence(
                user_id=user_id,
                signal_type=action_upper,
                target_type="STORY",
                target_id=str(story_id),
                target_name=article.title,
                source_article_id=article.id,
                source_story_id=story_id,
                commit=False,
            )
            evidence_list.append(ev)

        await self.session.commit()
        return evidence_list

    async def ingest_search_intent(
        self,
        user_id: uuid.UUID,
        query: str,
    ) -> List[UserInterestEvidence]:
        """
        Extracts topics/entities/keywords from a search query and records intent evidence.
        """
        cleaned_query = query.strip().lower()
        if not cleaned_query:
            return []

        words = [w for w in re.split(r"\W+", cleaned_query) if len(w) >= 3]
        evidence_list: List[UserInterestEvidence] = []

        # Find matching topics
        t_stmt = select(Topic)
        t_res = await self.session.execute(t_stmt)
        all_topics = list(t_res.scalars().all())
        matched_topics = [
            t for t in all_topics
            if t.name.lower() in cleaned_query or cleaned_query in t.name.lower() or any(w in t.name.lower() or w in t.slug.lower() for w in words)
        ]

        for t in matched_topics:
            ev = await self.record_evidence(
                user_id=user_id,
                signal_type="SEARCH",
                target_type="TOPIC",
                target_id=str(t.id),
                target_name=t.name,
                event_metadata={"query": query},
                commit=False,
            )
            evidence_list.append(ev)

        # Record high-signal keyword evidence
        for w in words[:3]:
            ev = await self.record_evidence(
                user_id=user_id,
                signal_type="SEARCH",
                target_type="KEYWORD",
                target_id=w,
                target_name=w,
                event_metadata={"query": query},
                commit=False,
            )
            evidence_list.append(ev)

        await self.session.commit()
        return evidence_list

    # =========================================================================
    # 2. Batch Evidence Aggregation & Preference Calculation
    # =========================================================================
    async def process_batch_learning(
        self, user_id: Optional[uuid.UUID] = None, limit: int = 500
    ) -> int:
        """
        Processes unprocessed evidence items in batch and updates topic/entity/keyword/source models.
        """
        query = (
            select(UserInterestEvidence)
            .where(UserInterestEvidence.processed == False)
            .order_by(UserInterestEvidence.created_at.asc())
            .limit(limit)
        )
        if user_id:
            query = query.where(UserInterestEvidence.user_id == user_id)

        res = await self.session.execute(query)
        evidence_items = list(res.scalars().all())
        if not evidence_items:
            return 0

        # Group by (user_id, target_type, target_id)
        user_ids: Set[uuid.UUID] = set()
        for ev in evidence_items:
            user_ids.add(ev.user_id)
            ev.processed = True

        await self.session.flush()

        # Re-aggregate each impacted user's preferences
        for uid in user_ids:
            await self._aggregate_user_preferences(uid)

        await self.session.commit()
        return len(evidence_items)

    async def _aggregate_user_preferences(self, user_id: uuid.UUID):
        """
        Aggregates all historical evidence for a user with time decay and evidence diversity.
        """
        now = utc_now()
        decay_short_lambda = math.log(2) / (self.SHORT_TERM_HALF_LIFE_DAYS * 86400.0)
        decay_long_lambda = math.log(2) / (self.LONG_TERM_HALF_LIFE_DAYS * 86400.0)

        # 1. Fetch all evidence for user
        ev_stmt = (
            select(UserInterestEvidence)
            .where(UserInterestEvidence.user_id == user_id)
            .order_by(UserInterestEvidence.created_at.asc())
        )
        ev_res = await self.session.execute(ev_stmt)
        all_evidence = list(ev_res.scalars().all())

        # Group by target_type
        topic_ev_map: Dict[str, List[UserInterestEvidence]] = {}
        entity_ev_map: Dict[str, List[UserInterestEvidence]] = {}
        keyword_ev_map: Dict[str, List[UserInterestEvidence]] = {}
        story_ev_map: Dict[str, List[UserInterestEvidence]] = {}

        for ev in all_evidence:
            if not ev.target_id:
                continue
            if ev.target_type == "TOPIC":
                topic_ev_map.setdefault(ev.target_id, []).append(ev)
            elif ev.target_type == "ENTITY":
                entity_ev_map.setdefault(ev.target_id, []).append(ev)
            elif ev.target_type == "KEYWORD":
                keyword_ev_map.setdefault(ev.target_id.lower(), []).append(ev)
            elif ev.target_type == "STORY":
                story_ev_map.setdefault(ev.target_id, []).append(ev)

        # 2. Update Topic Behavior Preferences
        for tid_str, ev_list in topic_ev_map.items():
            try:
                t_uuid = uuid.UUID(tid_str)
            except ValueError:
                continue

            # Calculate decay and diversity discounted scores
            pos_ev = sum(1 for e in ev_list if e.strength > 0 and not e.is_accidental)
            neg_ev = sum(1 for e in ev_list if e.strength < 0)
            story_counts: Dict[Any, int] = {}
            source_counts: Dict[Any, int] = {}

            short_term_sum = 0.0
            long_term_sum = 0.0

            for e in ev_list:
                age_secs = max(0.0, (now - ensure_utc(e.created_at)).total_seconds())
                w_short = math.exp(-decay_short_lambda * age_secs)
                w_long = math.exp(-decay_long_lambda * age_secs)

                # Evidence diversity discount: repeated signals on the same story saturate
                div_discount = 1.0
                if e.source_story_id:
                    st_cnt = story_counts.get(e.source_story_id, 0) + 1
                    story_counts[e.source_story_id] = st_cnt
                    div_discount = 1.0 / (1.0 + 0.35 * max(0, st_cnt - 1))

                effective_strength = e.strength * div_discount
                short_term_sum += effective_strength * w_short
                long_term_sum += effective_strength * w_long

            denom = max(1.0, float(len(ev_list)))
            st_score = max(-1.0, min(1.0, short_term_sum / denom))
            lt_score = max(-1.0, min(1.0, long_term_sum / denom))

            # Confidence calculation from diverse signals
            distinct_stories = len(story_counts)
            confidence = 1.0 - math.exp(
                -(pos_ev * 0.25 + neg_ev * 0.20 + distinct_stories * 0.15)
            )
            confidence = max(0.05, min(0.98, confidence))

            # Combined score: 65% long term + 35% short term
            combined_score = 0.65 * lt_score + 0.35 * st_score
            combined_score = max(-1.0, min(1.0, combined_score))

            # Upsert into UserTopicBehaviorPreference
            t_pref_stmt = select(UserTopicBehaviorPreference).where(
                UserTopicBehaviorPreference.user_id == user_id,
                UserTopicBehaviorPreference.topic_id == t_uuid,
            )
            tp_res = await self.session.execute(t_pref_stmt)
            t_pref = tp_res.scalars().first()

            if not t_pref:
                t_pref = UserTopicBehaviorPreference(
                    user_id=user_id,
                    topic_id=t_uuid,
                    score=combined_score,
                    confidence=confidence,
                    positive_evidence_count=pos_ev,
                    negative_evidence_count=neg_ev,
                    short_term_score=st_score,
                    long_term_score=lt_score,
                    distinct_story_count=distinct_stories,
                    last_signal_at=ensure_utc(ev_list[-1].created_at),
                    updated_at=now,
                )
                self.session.add(t_pref)
            else:
                t_pref.score = combined_score
                t_pref.confidence = confidence
                t_pref.positive_evidence_count = pos_ev
                t_pref.negative_evidence_count = neg_ev
                t_pref.short_term_score = st_score
                t_pref.long_term_score = lt_score
                t_pref.distinct_story_count = distinct_stories
                t_pref.last_signal_at = ensure_utc(ev_list[-1].created_at)
                t_pref.updated_at = now

        # 3. Update Entity Behavior Preferences
        for eid_str, ev_list in entity_ev_map.items():
            try:
                e_uuid = uuid.UUID(eid_str)
            except ValueError:
                continue

            pos_ev = sum(1 for e in ev_list if e.strength > 0 and not e.is_accidental)
            neg_ev = sum(1 for e in ev_list if e.strength < 0)
            score_sum = sum(e.strength for e in ev_list)
            ent_score = max(-1.0, min(1.0, score_sum / max(1.0, len(ev_list))))
            confidence = min(0.95, 0.10 + 0.15 * len(ev_list))

            ent_pref_stmt = select(UserEntityBehaviorPreference).where(
                UserEntityBehaviorPreference.user_id == user_id,
                UserEntityBehaviorPreference.entity_id == e_uuid,
            )
            ep_res = await self.session.execute(ent_pref_stmt)
            ep = ep_res.scalars().first()

            if not ep:
                ep = UserEntityBehaviorPreference(
                    user_id=user_id,
                    entity_id=e_uuid,
                    score=ent_score,
                    confidence=confidence,
                    positive_evidence_count=pos_ev,
                    negative_evidence_count=neg_ev,
                    short_term_score=ent_score,
                    long_term_score=ent_score,
                    last_signal_at=ensure_utc(ev_list[-1].created_at),
                    updated_at=now,
                )
                self.session.add(ep)
            else:
                ep.score = ent_score
                ep.confidence = confidence
                ep.positive_evidence_count = pos_ev
                ep.negative_evidence_count = neg_ev
                ep.updated_at = now

        # 4. Update Story Interest Signals
        for sid_str, ev_list in story_ev_map.items():
            try:
                s_uuid = uuid.UUID(sid_str)
            except ValueError:
                continue

            last_ev = ev_list[-1]
            last_time = ensure_utc(last_ev.created_at) or now
            expires_at = last_time + timedelta(hours=self.STORY_AFFINITY_EXPIRY_HOURS)

            s_sig_stmt = select(UserStoryInterestSignal).where(
                UserStoryInterestSignal.user_id == user_id,
                UserStoryInterestSignal.story_id == s_uuid,
            )
            s_res = await self.session.execute(s_sig_stmt)
            s_sig = s_res.scalars().first()

            if not s_sig:
                s_sig = UserStoryInterestSignal(
                    user_id=user_id,
                    story_id=s_uuid,
                    score=min(1.0, 0.50 + 0.15 * len(ev_list)),
                    interaction_count=len(ev_list),
                    last_signal_at=last_time,
                    expires_at=expires_at,
                )
                self.session.add(s_sig)
            else:
                s_sig.score = min(1.0, 0.50 + 0.15 * len(ev_list))
                s_sig.interaction_count = len(ev_list)
                s_sig.last_signal_at = last_time
                s_sig.expires_at = expires_at

        # 5. Clean up expired story signals
        del_stmt = delete(UserStoryInterestSignal).where(
            UserStoryInterestSignal.user_id == user_id,
            UserStoryInterestSignal.expires_at < now,
        )
        await self.session.execute(del_stmt)

    # =========================================================================
    # 3. Unified User Profile Assembly with Explicit Override
    # =========================================================================
    async def get_user_unified_profile(
        self, user_id: uuid.UUID
    ) -> UserProfileInterestsResponse:
        """
        Assembles the comprehensive user preference profile combining Explicit,
        Long-Term Behavioral, Short-Term, Entity, Keyword, and Story preferences.
        """
        now = utc_now()

        # 1. Fetch User Topic Behavior Preferences
        tp_stmt = (
            select(UserTopicBehaviorPreference)
            .options(selectinload(UserTopicBehaviorPreference.topic))
            .where(UserTopicBehaviorPreference.user_id == user_id)
        )
        tp_res = await self.session.execute(tp_stmt)
        topic_behaviors = list(tp_res.scalars().all())

        # 2. Fetch Explicit User Interests (legacy & topic preferences)
        exp_stmt = (
            select(UserInterest)
            .options(selectinload(UserInterest.topic))
            .where(UserInterest.user_id == user_id)
        )
        exp_res = await self.session.execute(exp_stmt)
        explicit_interests = list(exp_res.scalars().all())
        explicit_map = {
            ei.topic_id: ei for ei in explicit_interests if ei.topic
        }

        # Fetch Explicit Topic Preferences (Positive/Negative/Muted)
        pref_stmt = (
            select(UserTopicPreference)
            .options(selectinload(UserTopicPreference.topic))
            .where(UserTopicPreference.user_id == user_id)
        )
        pref_res = await self.session.execute(pref_stmt)
        topic_prefs = {tp.topic_id: tp for tp in pref_res.scalars().all() if tp.topic}

        # 3. Fetch Entity Preferences
        ent_stmt = (
            select(UserEntityBehaviorPreference)
            .options(selectinload(UserEntityBehaviorPreference.entity))
            .where(UserEntityBehaviorPreference.user_id == user_id)
            .order_by(desc(UserEntityBehaviorPreference.score))
            .limit(20)
        )
        ent_res = await self.session.execute(ent_stmt)
        entity_prefs = list(ent_res.scalars().all())

        # 4. Fetch Keyword Preferences
        kw_stmt = (
            select(UserKeywordBehaviorPreference)
            .where(UserKeywordBehaviorPreference.user_id == user_id)
            .order_by(desc(UserKeywordBehaviorPreference.score))
            .limit(15)
        )
        kw_res = await self.session.execute(kw_stmt)
        kw_prefs = list(kw_res.scalars().all())

        # 5. Fetch Active Story Affinities
        st_stmt = (
            select(UserStoryInterestSignal)
            .options(selectinload(UserStoryInterestSignal.story))
            .where(
                UserStoryInterestSignal.user_id == user_id,
                UserStoryInterestSignal.expires_at >= now,
            )
            .order_by(desc(UserStoryInterestSignal.score))
            .limit(10)
        )
        st_res = await self.session.execute(st_stmt)
        story_signals = list(st_res.scalars().all())

        # Combine all topics from behaviors and explicit interests
        all_topic_ids: Set[uuid.UUID] = set(explicit_map.keys()).union(
            tb.topic_id for tb in topic_behaviors
        ).union(topic_prefs.keys())

        # Fetch missing topics if any
        existing_tids = {tb.topic_id for tb in topic_behaviors if tb.topic}
        missing_tids = all_topic_ids - existing_tids
        if missing_tids:
            miss_stmt = select(Topic).where(Topic.id.in_(missing_tids))
            miss_res = await self.session.execute(miss_stmt)
            for mt in miss_res.scalars().all():
                # Add default neutral behavior item
                topic_behaviors.append(
                    UserTopicBehaviorPreference(
                        user_id=user_id,
                        topic_id=mt.id,
                        topic=mt,
                        score=0.0,
                        confidence=0.1,
                        positive_evidence_count=0,
                        negative_evidence_count=0,
                        short_term_score=0.0,
                        long_term_score=0.0,
                    )
                )

        strong_items: List[TopicInterestItem] = []
        growing_items: List[TopicInterestItem] = []
        low_engagement_items: List[TopicInterestItem] = []
        muted_items: List[TopicInterestItem] = []

        for tb in topic_behaviors:
            if not tb.topic:
                continue

            topic = tb.topic
            exp_item = explicit_map.get(topic.id)
            topic_pref = topic_prefs.get(topic.id)

            # Explicit override evaluation
            is_explicit_positive = (
                (exp_item and exp_item.preference_type == "POSITIVE")
                or (topic_pref and topic_pref.preference == "POSITIVE")
            )
            is_explicit_negative = (
                (exp_item and exp_item.preference_type == "NEGATIVE")
                or (topic_pref and topic_pref.preference == "NEGATIVE")
            )

            # Compute Unified Score (0.0 to 1.0 normalized)
            # Baseline behavior score (-1.0 to 1.0) -> mapped to 0.0 to 1.0
            behavior_norm = (tb.score + 1.0) / 2.0

            if is_explicit_negative:
                # OVERRIDE RULE: Explicit negative dominates completely
                unified_score = 0.0
                confidence = 1.0
                tier = "MUTED"
                explanation = "Explicitly marked not interested."
            elif is_explicit_positive:
                # Explicit positive boosts score high
                unified_score = min(1.0, 0.70 + 0.30 * behavior_norm)
                confidence = max(0.85, tb.confidence)
                tier = "STRONG" if unified_score >= 0.75 else "GROWING"
                explanation = f"Explicit interest + {tb.positive_evidence_count} engagement signals."
            else:
                # Pure behavioral inference
                unified_score = behavior_norm
                confidence = tb.confidence
                if (unified_score >= 0.65 and confidence >= 0.35) or (tb.positive_evidence_count >= 5):
                    tier = "STRONG"
                    explanation = f"High engagement across {tb.distinct_story_count} independent stories."
                elif unified_score > 0.50 or tb.short_term_score > 0.05 or tb.positive_evidence_count >= 1:
                    tier = "GROWING"
                    explanation = f"Rising engagement in recent reading activity."
                elif unified_score <= 0.45 or tb.negative_evidence_count >= 2:
                    tier = "LOW_ENGAGEMENT"
                    explanation = "Low recent engagement based on reading patterns."
                else:
                    tier = "GROWING"
                    explanation = "Moderate engagement history."

            item = TopicInterestItem(
                topic_id=topic.id,
                topic_name=topic.name,
                topic_slug=topic.slug,
                score=round(unified_score, 3),
                raw_behavior_score=round(tb.score, 3),
                confidence=round(confidence, 3),
                tier=tier,
                short_term_score=round(tb.short_term_score or 0.0, 3),
                long_term_score=round(tb.long_term_score or 0.0, 3),
                positive_evidence_count=tb.positive_evidence_count or 0,
                negative_evidence_count=tb.negative_evidence_count or 0,
                distinct_stories_count=tb.distinct_story_count or 0,
                distinct_sources_count=tb.distinct_source_count or 0,
                explicit_override="NEGATIVE" if is_explicit_negative else ("POSITIVE" if is_explicit_positive else None),
                last_signal_at=tb.last_signal_at,
                explanation=explanation,
            )

            if tier == "MUTED":
                muted_items.append(item)
            elif tier == "STRONG":
                strong_items.append(item)
            elif tier == "GROWING":
                growing_items.append(item)
            elif tier == "LOW_ENGAGEMENT":
                low_engagement_items.append(item)

        # Sort tiers
        strong_items.sort(key=lambda x: x.score, reverse=True)
        growing_items.sort(key=lambda x: x.short_term_score, reverse=True)
        low_engagement_items.sort(key=lambda x: x.score)

        # Build entity interest items
        ent_items = []
        for ep in entity_prefs:
            if not ep.entity:
                continue
            e_norm = (ep.score + 1.0) / 2.0
            ent_items.append(
                EntityInterestItem(
                    entity_id=ep.entity.id,
                    entity_name=ep.entity.name,
                    entity_type=ep.entity.entity_type,
                    score=round(e_norm, 3),
                    confidence=round(ep.confidence, 3),
                    positive_evidence_count=ep.positive_evidence_count,
                    negative_evidence_count=ep.negative_evidence_count,
                    explanation=f"Affinities learned from {ep.positive_evidence_count} mentions in articles read.",
                )
            )

        # Build keyword items
        kw_items = [
            KeywordInterestItem(
                keyword=kp.keyword,
                score=round((kp.score + 1.0) / 2.0, 3),
                confidence=round(kp.confidence, 3),
                interaction_count=kp.interaction_count,
            )
            for kp in kw_prefs
        ]

        # Active Story Affinities
        st_items = [
            StoryAffinityItem(
                story_id=ss.story.id,
                story_title=ss.story.title,
                score=round(ss.score, 3),
                expires_at=ss.expires_at,
            )
            for ss in story_signals if ss.story
        ]

        # Recent trending topics from short-term
        trending = [g.topic_name for g in growing_items[:4]]

        return UserProfileInterestsResponse(
            user_id=user_id,
            strong_interests=strong_items,
            growing_interests=growing_items,
            low_engagement_topics=low_engagement_items,
            muted_topics=muted_items,
            entity_preferences=ent_items,
            keyword_preferences=kw_items,
            active_story_affinities=st_items,
            recent_trending_topics=trending,
            exploration_factor=0.15,
            entropy_balance=0.85,
            last_rebuilt_at=now,
        )

    # =========================================================================
    # 4. Explicit User Overrides & Controls
    # =========================================================================
    async def apply_topic_override(
        self, user_id: uuid.UUID, req: TopicOverrideRequest
    ) -> TopicInterestItem:
        """
        Explicitly modifies a topic preference. Explicit user action overrides behavioral inferences.
        """
        action = req.override_action.upper().strip()
        now = utc_now()

        # Check Topic existence
        stmt = select(Topic).where(Topic.id == req.topic_id)
        res = await self.session.execute(stmt)
        topic = res.scalars().first()
        if not topic:
            raise ValueError(f"Topic {req.topic_id} not found")

        # Fetch or create UserTopicPreference (explicit override)
        pref_stmt = select(UserTopicPreference).where(
            UserTopicPreference.user_id == user_id,
            UserTopicPreference.topic_id == req.topic_id,
        )
        p_res = await self.session.execute(pref_stmt)
        tp = p_res.scalars().first()

        if action in ("MUTE", "SET_NEGATIVE", "DECREASE"):
            if not tp:
                tp = UserTopicPreference(
                    user_id=user_id,
                    topic_id=req.topic_id,
                    preference="NEGATIVE",
                    strength=1.0,
                    confidence=1.0,
                )
                self.session.add(tp)
            else:
                tp.preference = "NEGATIVE"
                tp.strength = 1.0

            # Record explicit negative evidence
            await self.record_evidence(
                user_id=user_id,
                signal_type="NOT_INTERESTED",
                target_type="TOPIC",
                target_id=str(topic.id),
                target_name=topic.name,
                commit=False,
            )

        elif action in ("SET_POSITIVE", "INCREASE", "FOLLOW"):
            if not tp:
                tp = UserTopicPreference(
                    user_id=user_id,
                    topic_id=req.topic_id,
                    preference="POSITIVE",
                    strength=1.0,
                    confidence=1.0,
                )
                self.session.add(tp)
            else:
                tp.preference = "POSITIVE"
                tp.strength = 1.0

            # Record explicit positive evidence
            await self.record_evidence(
                user_id=user_id,
                signal_type="EXPLICIT_INTEREST",
                target_type="TOPIC",
                target_id=str(topic.id),
                target_name=topic.name,
                commit=False,
            )

        elif action in ("REMOVE_OVERRIDE", "UNMUTE"):
            if tp:
                await self.session.delete(tp)

        await self.session.commit()
        await self._aggregate_user_preferences(user_id)
        await self.session.commit()

        # Return updated profile item
        profile = await self.get_user_unified_profile(user_id)
        for it in profile.strong_interests + profile.growing_interests + profile.low_engagement_topics + profile.muted_topics:
            if it.topic_id == req.topic_id:
                return it

        return TopicInterestItem(
            topic_id=topic.id,
            topic_name=topic.name,
            topic_slug=topic.slug,
            score=0.5,
            raw_behavior_score=0.0,
            confidence=0.1,
            tier="NEUTRAL",
            short_term_score=0.0,
            long_term_score=0.0,
            positive_evidence_count=0,
            negative_evidence_count=0,
            distinct_stories_count=0,
            distinct_sources_count=0,
            explanation="Neutral engagement.",
        )

    # =========================================================================
    # 5. Full Deterministic Profile Rebuild
    # =========================================================================
    async def rebuild_user_profile(self, user_id: uuid.UUID) -> ProfileRebuildResponse:
        """
        Recomputes the user's preference model from all stored behavioral evidence.
        Clears derived preference tables and replays evidence chronologically.
        """
        start_time = datetime.now()

        # 1. Clear derived behavior preference rows for user
        await self.session.execute(
            delete(UserTopicBehaviorPreference).where(UserTopicBehaviorPreference.user_id == user_id)
        )
        await self.session.execute(
            delete(UserEntityBehaviorPreference).where(UserEntityBehaviorPreference.user_id == user_id)
        )
        await self.session.execute(
            delete(UserKeywordBehaviorPreference).where(UserKeywordBehaviorPreference.user_id == user_id)
        )
        await self.session.execute(
            delete(UserStoryInterestSignal).where(UserStoryInterestSignal.user_id == user_id)
        )
        await self.session.flush()

        # 2. Reset processed flag on all user evidence
        await self.session.execute(
            update(UserInterestEvidence)
            .where(UserInterestEvidence.user_id == user_id)
            .values(processed=False)
        )
        await self.session.commit()

        # 3. Re-run aggregation
        processed_count = await self.process_batch_learning(user_id=user_id, limit=5000)

        # Count updated rows
        t_cnt_stmt = select(func.count(UserTopicBehaviorPreference.id)).where(UserTopicBehaviorPreference.user_id == user_id)
        e_cnt_stmt = select(func.count(UserEntityBehaviorPreference.id)).where(UserEntityBehaviorPreference.user_id == user_id)
        k_cnt_stmt = select(func.count(UserKeywordBehaviorPreference.id)).where(UserKeywordBehaviorPreference.user_id == user_id)

        t_cnt = (await self.session.execute(t_cnt_stmt)).scalar() or 0
        e_cnt = (await self.session.execute(e_cnt_stmt)).scalar() or 0
        k_cnt = (await self.session.execute(k_cnt_stmt)).scalar() or 0

        duration = (datetime.now() - start_time).total_seconds() * 1000.0

        return ProfileRebuildResponse(
            user_id=user_id,
            status="SUCCESS",
            evidence_events_processed=processed_count,
            topics_updated=t_cnt,
            entities_updated=e_cnt,
            keywords_updated=k_cnt,
            duration_ms=round(duration, 2),
            rebuilt_at=utc_now(),
        )
