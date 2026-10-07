"""control_center_service.py — Phase 23 Personalization Control Center Service.

Implements transparent user controls, human-readable explanations, topic/entity/source
preferences, learning state toggles, and safe profile reset/rebuild.
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy import select, and_, or_, desc, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.topic import Topic
from app.models.entity import Entity
from app.models.article import Article
from app.models.source import NewsSource
from app.models.interest import UserInterest
from app.models.interest_profile import UserTopicPreference
from app.models.action import UserArticleAction
from app.models.reading_history import ReadingHistory
from app.models.personalization_settings import UserPersonalizationSettings
from app.source_intelligence.models import UserSourcePreference, UserSourceAffinity
from app.story_intelligence.models import Story
from app.learning.evidence_models import (
    UserInterestEvidence,
    UserTopicBehaviorPreference,
    UserEntityBehaviorPreference,
    UserKeywordBehaviorPreference,
    UserStoryInterestSignal,
)
from app.learning.behavioral_engine import BehavioralLearningEngine
from app.schemas.personalization import (
    PersonalizationSettingsResponse,
    PersonalizationSettingsUpdate,
    ExplicitInterestItem,
    InferredInterestItem,
    TopicControlItem,
    EntityControlItem,
    SourceControlItem,
    TemporaryInterestItem,
    WhyThisStoryResponse,
    PersonalizationProfileResponse,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PersonalizationControlCenterService:
    """Service providing end-to-end control and transparency over user personalization."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.learning_engine = BehavioralLearningEngine(session)

    # =========================================================================
    # 1. Settings Management
    # =========================================================================
    async def get_or_create_settings(self, user_id: uuid.UUID) -> UserPersonalizationSettings:
        stmt = select(UserPersonalizationSettings).where(UserPersonalizationSettings.user_id == user_id)
        res = await self.session.execute(stmt)
        settings_obj = res.scalar_one_or_none()

        if not settings_obj:
            now = utc_now()
            settings_obj = UserPersonalizationSettings(
                id=uuid.uuid4(),
                user_id=user_id,
                discovery_level="BALANCED",
                personalization_strength="BALANCED",
                diversity_level="BALANCED",
                learning_enabled=True,
                section_preferences={
                    "TOP_STORIES": "SHOW",
                    "TECHNOLOGY": "SHOW",
                    "BUSINESS": "SHOW",
                    "SCIENCE": "SHOW",
                    "WORLD": "SHOW",
                    "INDIA": "SHOW",
                    "SPORTS": "SHOW",
                    "ENTERTAINMENT": "SHOW",
                    "DISCOVER": "SHOW",
                },
                created_at=now,
                updated_at=now,
            )
            self.session.add(settings_obj)
            await self.session.commit()
            await self.session.refresh(settings_obj)

        return settings_obj

    async def update_settings(
        self, user_id: uuid.UUID, update_data: PersonalizationSettingsUpdate
    ) -> UserPersonalizationSettings:
        settings_obj = await self.get_or_create_settings(user_id)
        if update_data.discovery_level is not None:
            settings_obj.discovery_level = update_data.discovery_level
        if update_data.personalization_strength is not None:
            settings_obj.personalization_strength = update_data.personalization_strength
        if update_data.diversity_level is not None:
            settings_obj.diversity_level = update_data.diversity_level
        if update_data.learning_enabled is not None:
            settings_obj.learning_enabled = update_data.learning_enabled
        if update_data.section_preferences is not None:
            current = dict(settings_obj.section_preferences or {})
            current.update(update_data.section_preferences)
            settings_obj.section_preferences = current

        settings_obj.updated_at = utc_now()
        await self.session.commit()
        await self.session.refresh(settings_obj)
        return settings_obj

    # =========================================================================
    # 2. Comprehensive Profile & Transparency
    # =========================================================================
    async def get_personalization_profile(self, user_id: uuid.UUID) -> PersonalizationProfileResponse:
        settings_obj = await self.get_or_create_settings(user_id)

        # 1. Explicit Interests
        stmt_explicit = (
            select(UserInterest)
            .options(selectinload(UserInterest.topic))
            .where(UserInterest.user_id == user_id)
            .order_by(desc(UserInterest.interest_score))
        )
        res_explicit = await self.session.execute(stmt_explicit)
        explicit_rows = list(res_explicit.scalars().all())

        explicit_items = [
            ExplicitInterestItem(
                id=r.id,
                topic_id=r.topic_id,
                topic_name=r.topic.name if r.topic else "General",
                topic_slug=r.topic.slug if r.topic else "general",
                preference_type=r.preference_type,
                interest_score=r.interest_score,
                source=r.source,
                created_at=r.created_at,
            )
            for r in explicit_rows
            if r.preference_type == "POSITIVE"
        ]

        # 2. Inferred Behavioral Topic Preferences
        stmt_inferred = (
            select(UserTopicBehaviorPreference)
            .options(selectinload(UserTopicBehaviorPreference.topic))
            .where(UserTopicBehaviorPreference.user_id == user_id)
            .order_by(desc(UserTopicBehaviorPreference.score))
        )
        res_inferred = await self.session.execute(stmt_inferred)
        inferred_rows = list(res_inferred.scalars().all())

        inferred_items: List[InferredInterestItem] = []
        for r in inferred_rows:
            # Human tier
            if r.score >= 0.6 and r.confidence >= 0.4:
                tier = "Strong interest"
            elif r.short_term_score >= 0.4:
                tier = "Growing interest"
            elif r.score >= 0.2:
                tier = "Moderate interest"
            else:
                tier = "Low recent interest"

            # Human why reason
            why = f"Based on {r.positive_evidence_count} articles read across {r.distinct_story_count} developing stories."
            if r.short_term_score >= 0.5:
                why += " High recent reading engagement."

            inferred_items.append(
                InferredInterestItem(
                    topic_id=r.topic_id,
                    topic_name=r.topic.name if r.topic else "General",
                    topic_slug=r.topic.slug if r.topic else "general",
                    tier=tier,
                    why_reason=why,
                    reads_count=r.positive_evidence_count,
                    saves_count=0,
                    searches_count=0,
                    completion_avg=round(min(1.0, r.score), 2),
                )
            )

        # 3. Topic Management (Following, Muted, Suggested)
        following_topics: List[TopicControlItem] = []
        muted_topics: List[TopicControlItem] = []
        suggested_topics: List[TopicControlItem] = []

        # Explicit overrides
        stmt_topic_prefs = (
            select(UserTopicPreference)
            .options(selectinload(UserTopicPreference.topic))
            .where(UserTopicPreference.user_id == user_id)
        )
        res_tprefs = await self.session.execute(stmt_topic_prefs)
        tprefs = list(res_tprefs.scalars().all())

        followed_ids = {tp.topic_id for tp in tprefs if tp.preference == "POSITIVE"}
        muted_ids = {tp.topic_id for tp in tprefs if tp.preference == "NEGATIVE"}

        # Also include explicit user interests
        for r in explicit_rows:
            if r.preference_type == "POSITIVE":
                followed_ids.add(r.topic_id)
            elif r.preference_type == "NEGATIVE":
                muted_ids.add(r.topic_id)

        # Fetch all known topics
        stmt_all_topics = select(Topic).options(selectinload(Topic.parent_topic)).order_by(Topic.name)
        res_all_topics = await self.session.execute(stmt_all_topics)
        all_topics = list(res_all_topics.scalars().all())

        for t in all_topics:
            parent_name = t.parent_topic.name if getattr(t, "parent_topic", None) else None
            if t.id in followed_ids:
                following_topics.append(
                    TopicControlItem(
                        topic_id=t.id,
                        topic_name=t.name,
                        topic_slug=t.slug,
                        parent_id=getattr(t, "parent_topic_id", None),
                        parent_name=parent_name,
                        status="FOLLOWING",
                        strength_label="Strong",
                        why_reason="Explicitly followed by you",
                    )
                )
            elif t.id in muted_ids:
                muted_topics.append(
                    TopicControlItem(
                        topic_id=t.id,
                        topic_name=t.name,
                        topic_slug=t.slug,
                        parent_id=getattr(t, "parent_topic_id", None),
                        parent_name=parent_name,
                        status="MUTED",
                        strength_label="Muted",
                        why_reason="Muted by your preference",
                    )
                )
            else:
                # Check if behavior shows high affinity
                b_pref = next((bp for bp in inferred_rows if bp.topic_id == t.id), None)
                if b_pref and b_pref.score >= 0.3:
                    suggested_topics.append(
                        TopicControlItem(
                            topic_id=t.id,
                            topic_name=t.name,
                            topic_slug=t.slug,
                            parent_id=getattr(t, "parent_topic_id", None),
                            parent_name=parent_name,
                            status="SUGGESTED",
                            strength_label="Growing",
                            why_reason=f"Suggested based on your {b_pref.positive_evidence_count} recent reads",
                        )
                    )

        # 4. Entities
        stmt_entities = (
            select(UserEntityBehaviorPreference)
            .options(selectinload(UserEntityBehaviorPreference.entity))
            .where(UserEntityBehaviorPreference.user_id == user_id)
            .order_by(desc(UserEntityBehaviorPreference.score))
            .limit(20)
        )
        res_ent = await self.session.execute(stmt_entities)
        ent_rows = list(res_ent.scalars().all())

        entity_items: List[EntityControlItem] = []
        for e in ent_rows:
            if not e.entity:
                continue
            e_status = "MUTED" if e.score < -0.3 else ("FOLLOWING" if e.score >= 0.6 else "NEUTRAL")
            why_e = f"{e.positive_evidence_count} articles read across {e.distinct_story_count} stories."
            entity_items.append(
                EntityControlItem(
                    entity_id=e.entity_id,
                    name=e.entity.name,
                    entity_type=e.entity.entity_type if hasattr(e.entity, "entity_type") else "ENTITY",
                    status=e_status,
                    interaction_count=e.positive_evidence_count,
                    why_reason=why_e,
                )
            )

        # 5. Sources
        stmt_sources = (
            select(UserSourceAffinity)
            .options(selectinload(UserSourceAffinity.source))
            .where(UserSourceAffinity.user_id == user_id)
            .order_by(desc(UserSourceAffinity.score))
            .limit(20)
        )
        res_sources = await self.session.execute(stmt_sources)
        source_rows = list(res_sources.scalars().all())

        # Check explicit source preferences
        stmt_sprefs = select(UserSourcePreference).where(UserSourcePreference.user_id == user_id)
        res_sprefs = await self.session.execute(stmt_sprefs)
        sprefs = {sp.source_id: sp for sp in res_sprefs.scalars().all()}

        source_items: List[SourceControlItem] = []
        for s in source_rows:
            if not s.source:
                continue
            sp = sprefs.get(s.source_id)
            s_status = "MUTED" if (sp and sp.is_muted) else ("PREFERRED" if (sp and sp.is_following) else "NEUTRAL")
            affinity_lbl = "High Affinity" if s.score >= 0.7 else ("Moderate" if s.score >= 0.4 else "Regular")
            source_items.append(
                SourceControlItem(
                    source_id=s.source_id,
                    name=s.source.name,
                    domain=getattr(s.source, "domain", None),
                    status=s_status,
                    read_count=s.evidence_count,
                    affinity_label=affinity_lbl,
                )
            )

        # 6. Temporary / Trending Interests
        now = utc_now()
        stmt_temp = (
            select(UserStoryInterestSignal)
            .options(selectinload(UserStoryInterestSignal.story))
            .where(
                UserStoryInterestSignal.user_id == user_id,
                UserStoryInterestSignal.expires_at > now,
            )
            .order_by(desc(UserStoryInterestSignal.score))
            .limit(10)
        )
        res_temp = await self.session.execute(stmt_temp)
        temp_rows = list(res_temp.scalars().all())

        temporary_items = [
            TemporaryInterestItem(
                story_id=t.story_id,
                title=t.story.title if t.story else "Developing Story",
                topic_name=t.story.primary_topic.name if (t.story and t.story.primary_topic) else None,
                interaction_count=t.interaction_count,
                expires_at=t.expires_at,
            )
            for t in temp_rows
        ]

        # 7. Learning Stats & Transparency
        cnt_reads = (await self.session.execute(
            select(func.count(ReadingHistory.id)).where(ReadingHistory.user_id == user_id)
        )).scalar() or 0

        cnt_actions = (await self.session.execute(
            select(func.count(UserArticleAction.id)).where(UserArticleAction.user_id == user_id)
        )).scalar() or 0

        learning_stats = {
            "articles_read": cnt_reads,
            "actions_recorded": cnt_actions,
            "topics_followed": len(following_topics),
            "topics_muted": len(muted_topics),
            "inferred_interests_count": len(inferred_items),
        }

        privacy_transparency = {
            "learning_enabled": settings_obj.learning_enabled,
            "data_types_used": [
                "Articles read & reading duration",
                "Articles completed & scroll depth",
                "Saved & liked articles",
                "Search keywords & topics",
                "Explicit followed & muted preferences",
            ],
            "data_isolation_guarantee": "Strict per-user data isolation. No shared private profiles.",
        }

        return PersonalizationProfileResponse(
            explicit_interests=explicit_items,
            inferred_interests=inferred_items,
            following_topics=following_topics,
            muted_topics=muted_topics,
            suggested_topics=suggested_topics,
            entities=entity_items,
            sources=source_items,
            temporary_interests=temporary_items,
            settings=PersonalizationSettingsResponse.model_validate(settings_obj),
            learning_stats=learning_stats,
            privacy_transparency=privacy_transparency,
        )

    # =========================================================================
    # 3. Topic, Entity & Source Management
    # =========================================================================
    async def manage_topic(self, user_id: uuid.UUID, topic_id: uuid.UUID, action: str) -> Dict[str, Any]:
        """Manages a topic with explicit user precedence."""
        action = action.upper().strip()
        stmt = select(Topic).where(Topic.id == topic_id)
        topic = (await self.session.execute(stmt)).scalar_one_or_none()
        if not topic:
            raise ValueError(f"Topic {topic_id} not found")

        # Explicit UserTopicPreference
        pref_stmt = select(UserTopicPreference).where(
            UserTopicPreference.user_id == user_id,
            UserTopicPreference.topic_id == topic_id,
        )
        res_p = await self.session.execute(pref_stmt)
        tp = res_p.scalar_one_or_none()

        # Explicit UserInterest
        int_stmt = select(UserInterest).where(
            UserInterest.user_id == user_id,
            UserInterest.topic_id == topic_id,
        )
        res_i = await self.session.execute(int_stmt)
        ui = res_i.scalar_one_or_none()

        if action in ("FOLLOW", "SET_POSITIVE"):
            if not tp:
                tp = UserTopicPreference(user_id=user_id, topic_id=topic_id, preference="POSITIVE", strength=1.0)
                self.session.add(tp)
            else:
                tp.preference = "POSITIVE"
                tp.strength = 1.0

            if not ui:
                ui = UserInterest(user_id=user_id, topic_id=topic_id, preference_type="POSITIVE", interest_score=1.0, source="USER_ACTION")
                self.session.add(ui)
            else:
                ui.preference_type = "POSITIVE"
                ui.interest_score = 1.0

            await self.learning_engine.record_evidence(
                user_id=user_id, signal_type="EXPLICIT_INTEREST", target_type="TOPIC", target_id=str(topic_id), target_name=topic.name, commit=False
            )

        elif action in ("MUTE", "NOT_INTERESTED", "SET_NEGATIVE"):
            if not tp:
                tp = UserTopicPreference(user_id=user_id, topic_id=topic_id, preference="NEGATIVE", strength=1.0)
                self.session.add(tp)
            else:
                tp.preference = "NEGATIVE"
                tp.strength = 1.0

            if not ui:
                ui = UserInterest(user_id=user_id, topic_id=topic_id, preference_type="NEGATIVE", interest_score=0.0, source="USER_ACTION")
                self.session.add(ui)
            else:
                ui.preference_type = "NEGATIVE"
                ui.interest_score = 0.0

            await self.learning_engine.record_evidence(
                user_id=user_id, signal_type="NOT_INTERESTED", target_type="TOPIC", target_id=str(topic_id), target_name=topic.name, commit=False
            )

        elif action in ("UNMUTE", "REMOVE_OVERRIDE"):
            if tp:
                await self.session.delete(tp)
            if ui and ui.preference_type == "NEGATIVE":
                await self.session.delete(ui)

        elif action == "MORE":
            # Increase behavioral preference
            stmt_bp = select(UserTopicBehaviorPreference).where(
                UserTopicBehaviorPreference.user_id == user_id,
                UserTopicBehaviorPreference.topic_id == topic_id,
            )
            bp = (await self.session.execute(stmt_bp)).scalar_one_or_none()
            if bp:
                bp.score = min(1.0, bp.score + 0.3)
                bp.positive_evidence_count += 1
            await self.learning_engine.record_evidence(
                user_id=user_id, signal_type="LIKE", target_type="TOPIC", target_id=str(topic_id), target_name=topic.name, commit=False
            )

        elif action == "LESS":
            # Decrease behavioral preference
            stmt_bp = select(UserTopicBehaviorPreference).where(
                UserTopicBehaviorPreference.user_id == user_id,
                UserTopicBehaviorPreference.topic_id == topic_id,
            )
            bp = (await self.session.execute(stmt_bp)).scalar_one_or_none()
            if bp:
                bp.score = max(-1.0, bp.score - 0.3)
                bp.negative_evidence_count += 1
            await self.learning_engine.record_evidence(
                user_id=user_id, signal_type="SKIP", target_type="TOPIC", target_id=str(topic_id), target_name=topic.name, commit=False
            )

        await self.session.commit()
        return {"status": "SUCCESS", "topic_id": str(topic_id), "action": action}

    async def manage_entity(self, user_id: uuid.UUID, entity_id: uuid.UUID, action: str) -> Dict[str, Any]:
        """Manages entity follow, mute, and preference adjustments."""
        action = action.upper().strip()
        stmt = select(Entity).where(Entity.id == entity_id)
        entity = (await self.session.execute(stmt)).scalar_one_or_none()
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        stmt_bp = select(UserEntityBehaviorPreference).where(
            UserEntityBehaviorPreference.user_id == user_id,
            UserEntityBehaviorPreference.entity_id == entity_id,
        )
        bp = (await self.session.execute(stmt_bp)).scalar_one_or_none()

        if action == "FOLLOW":
            if not bp:
                bp = UserEntityBehaviorPreference(user_id=user_id, entity_id=entity_id, score=1.0, confidence=1.0, positive_evidence_count=1)
                self.session.add(bp)
            else:
                bp.score = 1.0
                bp.confidence = 1.0

        elif action in ("MUTE", "NOT_INTERESTED"):
            if not bp:
                bp = UserEntityBehaviorPreference(user_id=user_id, entity_id=entity_id, score=-1.0, confidence=1.0, negative_evidence_count=1)
                self.session.add(bp)
            else:
                bp.score = -1.0
                bp.confidence = 1.0

        elif action == "LESS":
            if bp:
                bp.score = max(-1.0, bp.score - 0.4)

        elif action == "UNMUTE":
            if bp:
                bp.score = 0.0

        await self.session.commit()
        return {"status": "SUCCESS", "entity_id": str(entity_id), "action": action}

    async def manage_source(self, user_id: uuid.UUID, source_id: uuid.UUID, action: str) -> Dict[str, Any]:
        """Manages news source follow, mute, and reduce preferences."""
        action = action.upper().strip()
        stmt = select(NewsSource).where(NewsSource.id == source_id)
        src = (await self.session.execute(stmt)).scalar_one_or_none()
        if not src:
            raise ValueError(f"Source {source_id} not found")

        stmt_sp = select(UserSourcePreference).where(
            UserSourcePreference.user_id == user_id,
            UserSourcePreference.source_id == source_id,
        )
        sp = (await self.session.execute(stmt_sp)).scalar_one_or_none()

        if action == "PREFER":
            if not sp:
                sp = UserSourcePreference(user_id=user_id, source_id=source_id, is_following=True, is_muted=False)
                self.session.add(sp)
            else:
                sp.is_following = True
                sp.is_muted = False

        elif action == "MUTE":
            if not sp:
                sp = UserSourcePreference(user_id=user_id, source_id=source_id, is_following=False, is_muted=True)
                self.session.add(sp)
            else:
                sp.is_following = False
                sp.is_muted = True

        elif action == "UNMUTE":
            if sp:
                sp.is_muted = False

        elif action == "REDUCE":
            stmt_aff = select(UserSourceAffinity).where(
                UserSourceAffinity.user_id == user_id,
                UserSourceAffinity.source_id == source_id,
            )
            aff = (await self.session.execute(stmt_aff)).scalar_one_or_none()
            if aff:
                aff.score = max(0.0, aff.score - 0.3)

        await self.session.commit()
        return {"status": "SUCCESS", "source_id": str(source_id), "action": action}

    # =========================================================================
    # 4. "Why Am I Seeing This?" Story Explanation
    # =========================================================================
    async def explain_why_story(self, user_id: uuid.UUID, article_id: uuid.UUID) -> WhyThisStoryResponse:
        """Constructs 1-3 human-readable reasons for why an article is recommended."""
        stmt = (
            select(Article)
            .options(
                selectinload(Article.topics),
                selectinload(Article.source),
            )
            .where(Article.id == article_id)
        )
        res = await self.session.execute(stmt)
        art = res.scalar_one_or_none()
        if not art:
            raise ValueError(f"Article {article_id} not found")

        primary_topic = art.topics[0] if art.topics else None
        reasons: List[str] = []
        is_breaking_override = False

        # 1. Check explicit followed topic
        if primary_topic:
            stmt_ui = select(UserInterest).where(
                UserInterest.user_id == user_id,
                UserInterest.topic_id == primary_topic.id,
                UserInterest.preference_type == "POSITIVE",
            )
            ui = (await self.session.execute(stmt_ui)).scalar_one_or_none()
            if ui:
                reasons.append(f"You follow the topic '{primary_topic.name}'.")

            # Check high behavioral affinity
            stmt_bp = select(UserTopicBehaviorPreference).where(
                UserTopicBehaviorPreference.user_id == user_id,
                UserTopicBehaviorPreference.topic_id == primary_topic.id,
            )
            bp = (await self.session.execute(stmt_bp)).scalar_one_or_none()
            if bp and bp.score >= 0.4:
                reasons.append(f"You frequently read and engage with stories in '{primary_topic.name}'.")

        # 2. Check preferred source
        if art.source_id:
            stmt_sp = select(UserSourcePreference).where(
                UserSourcePreference.user_id == user_id,
                UserSourcePreference.source_id == art.source_id,
                UserSourcePreference.is_following.is_(True),
            )
            sp = (await self.session.execute(stmt_sp)).scalar_one_or_none()
            if sp and art.source:
                reasons.append(f"Published by '{art.source.name}', one of your preferred news sources.")

        # 3. Check breaking or global importance
        if getattr(art, "quality_score", 0.0) >= 0.85:
            reasons.append("High editorial importance and verified multi-source reporting.")

        # If muted topic but shown due to critical breaking news
        if primary_topic:
            stmt_muted = select(UserInterest).where(
                UserInterest.user_id == user_id,
                UserInterest.topic_id == primary_topic.id,
                UserInterest.preference_type == "NEGATIVE",
            )
            muted = (await self.session.execute(stmt_muted)).scalar_one_or_none()
            if muted:
                is_breaking_override = True
                reasons = ["Important global update included despite muted topic preference."]

        # Fallback discovery reason
        if not reasons:
            reasons.append("Curated for balanced discovery in your personalized edition.")

        primary_reason = reasons[0]
        return WhyThisStoryResponse(
            article_id=article_id,
            title=art.title,
            primary_reason=primary_reason,
            reasons=reasons[:3],
            topic_id=primary_topic.id if primary_topic else None,
            topic_name=primary_topic.name if primary_topic else None,
            source_name=art.source.name if art.source else None,
            is_breaking_override=is_breaking_override,
        )

    # =========================================================================
    # 5. Learning State, Reset & Rebuild
    # =========================================================================
    async def pause_learning(self, user_id: uuid.UUID) -> Dict[str, Any]:
        settings_obj = await self.get_or_create_settings(user_id)
        settings_obj.learning_enabled = False
        settings_obj.updated_at = utc_now()
        await self.session.commit()
        return {"status": "SUCCESS", "learning_enabled": False}

    async def resume_learning(self, user_id: uuid.UUID) -> Dict[str, Any]:
        settings_obj = await self.get_or_create_settings(user_id)
        settings_obj.learning_enabled = True
        settings_obj.updated_at = utc_now()
        await self.session.commit()
        return {"status": "SUCCESS", "learning_enabled": True}

    async def reset_personalization(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Resets derived behavioral preferences while keeping saved articles & explicit interests."""
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
        await self.session.execute(
            delete(UserSourceAffinity).where(UserSourceAffinity.user_id == user_id)
        )
        await self.session.commit()
        logger.info(f"User {user_id} reset personalization profile successfully.")
        return {"status": "SUCCESS", "message": "Personalization profile reset successfully."}

    async def rebuild_personalization(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Reconstructs derived preference profiles from stored evidence."""
        res = await self.learning_engine.rebuild_user_profile(user_id)
        return {
            "status": res.status,
            "evidence_events_processed": res.evidence_events_processed,
            "topics_updated": res.topics_updated,
            "duration_ms": res.duration_ms,
        }

    async def clear_temporary_interests(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Clears short-term story affinity signals and resets short-term boosts."""
        await self.session.execute(
            delete(UserStoryInterestSignal).where(UserStoryInterestSignal.user_id == user_id)
        )
        await self.session.execute(
            update(UserTopicBehaviorPreference)
            .where(UserTopicBehaviorPreference.user_id == user_id)
            .values(short_term_score=0.0, session_boost_score=0.0)
        )
        await self.session.commit()
        return {"status": "SUCCESS", "message": "Temporary and trending interests cleared."}
