"""candidate_generator.py — Candidate Generation from Multiple Profile & Behavioral Sources."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, desc
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.article import Article, article_topics
from app.models.topic import Topic
from app.models.entity import Entity, article_entities
from app.models.analysis import ArticleAnalysis
from app.models.reading_history import ReadingHistory
from app.personalization.services.personalization_service import PersonalizationService
from app.personalization.schemas import UserInterestProfile

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CandidateGenerator:
    """Generates 100–300 candidate articles from 6 multi-dimensional profile and behavioral sources."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.personalization_service = PersonalizationService(session)

    async def generate_candidates(
        self,
        user_id: uuid.UUID,
        target_pool_size: int = 200,
        max_age_hours: int = settings.RECOMMENDATION_MAX_AGE_HOURS,
    ) -> Tuple[List[Article], UserInterestProfile, Dict[uuid.UUID, str]]:
        """
        Retrieves candidate articles from 6 sources:
        1. Semantic similarity
        2. Topic interests
        3. Entity interests
        4. Emerging interests
        5. Recently read articles
        6. Trending within user's interests

        Returns: (candidate_articles, user_profile, article_source_reasons)
        """
        now = utc_now()
        recency_cutoff = now - timedelta(hours=max_age_hours)

        profile = await self.personalization_service.get_user_interest_profile(user_id)
        candidate_map: Dict[uuid.UUID, Article] = {}
        reason_map: Dict[uuid.UUID, str] = {}

        # ---------------------------------------------------------------------
        # Cold Start Check
        # ---------------------------------------------------------------------
        if not profile.has_interests:
            logger.info(f"Cold start candidate generation for user {user_id}")
            stmt_cold = (
                select(Article)
                .where(
                    Article.status == "PUBLISHED",
                    Article.published_at >= recency_cutoff,
                )
                .options(
                    selectinload(Article.topics),
                    selectinload(Article.analysis),
                    selectinload(Article.entities),
                    selectinload(Article.keywords),
                )
                .order_by(desc(Article.published_at))
                .limit(target_pool_size)
            )
            res_cold = await self.session.execute(stmt_cold)
            cold_articles = list(res_cold.scalars().all())

            # Fallback if no recent articles in cutoff window
            if len(cold_articles) < 10:
                stmt_fallback = (
                    select(Article)
                    .where(Article.status == "PUBLISHED")
                    .options(
                        selectinload(Article.topics),
                        selectinload(Article.analysis),
                        selectinload(Article.entities),
                        selectinload(Article.keywords),
                    )
                    .order_by(desc(Article.created_at))
                    .limit(target_pool_size)
                )
                res_fallback = await self.session.execute(stmt_fallback)
                cold_articles = list(res_fallback.scalars().all())

            for art in cold_articles:
                candidate_map[art.id] = art
                reason_map[art.id] = "DISCOVERY"

            return list(candidate_map.values()), profile, reason_map

        # ---------------------------------------------------------------------
        # SOURCE 2: Topic Interests (Top Positive Topics)
        # ---------------------------------------------------------------------
        if profile.positive_interests:
            top_topic_slugs = list(profile.positive_interests.keys())[:10]
            stmt_topic = (
                select(Article)
                .join(article_topics)
                .join(Topic)
                .where(
                    Article.status == "PUBLISHED",
                    Article.published_at >= recency_cutoff,
                    Topic.slug.in_(top_topic_slugs),
                )
                .options(
                    selectinload(Article.topics),
                    selectinload(Article.analysis),
                    selectinload(Article.entities),
                    selectinload(Article.keywords),
                )
                .order_by(desc(Article.published_at))
                .limit(100)
            )
            res_topic = await self.session.execute(stmt_topic)
            for art in res_topic.scalars().all():
                if art.id not in candidate_map:
                    candidate_map[art.id] = art
                    reason_map[art.id] = "STRONG_INTEREST"

        # ---------------------------------------------------------------------
        # SOURCE 3: Entity Interests (Learned Preferred Entities)
        # ---------------------------------------------------------------------
        if profile.learned_entities:
            top_entities = sorted(profile.learned_entities.items(), key=lambda x: x[1], reverse=True)[:10]
            top_entity_names = [e[0] for e in top_entities]
            stmt_ent = (
                select(Article)
                .join(article_entities)
                .join(Entity)
                .where(
                    Article.status == "PUBLISHED",
                    Article.published_at >= recency_cutoff,
                    Entity.normalized_name.in_(top_entity_names),
                )
                .options(
                    selectinload(Article.topics),
                    selectinload(Article.analysis),
                    selectinload(Article.entities),
                    selectinload(Article.keywords),
                )
                .limit(60)
            )
            res_ent = await self.session.execute(stmt_ent)
            for art in res_ent.scalars().all():
                if art.id not in candidate_map:
                    candidate_map[art.id] = art
                    reason_map[art.id] = "RELATED_TO_READING"

        # ---------------------------------------------------------------------
        # SOURCE 4 & 5: Emerging Interests & Recently Read Articles
        # ---------------------------------------------------------------------
        stmt_read = (
            select(ReadingHistory)
            .options(selectinload(ReadingHistory.article).selectinload(Article.topics))
            .where(ReadingHistory.user_id == user_id)
            .order_by(desc(ReadingHistory.last_read_at))
            .limit(5)
        )
        res_read = await self.session.execute(stmt_read)
        recent_reads = list(res_read.scalars().all())

        read_topic_slugs: Set[str] = set()
        for rr in recent_reads:
            if rr.article and rr.article.topics:
                for t in rr.article.topics:
                    read_topic_slugs.add(t.slug)

        if read_topic_slugs:
            stmt_rr = (
                select(Article)
                .join(article_topics)
                .join(Topic)
                .where(
                    Article.status == "PUBLISHED",
                    Article.published_at >= recency_cutoff,
                    Topic.slug.in_(list(read_topic_slugs)),
                )
                .options(
                    selectinload(Article.topics),
                    selectinload(Article.analysis),
                    selectinload(Article.entities),
                    selectinload(Article.keywords),
                )
                .limit(60)
            )
            res_rr = await self.session.execute(stmt_rr)
            for art in res_rr.scalars().all():
                if art.id not in candidate_map:
                    candidate_map[art.id] = art
                    reason_map[art.id] = "EMERGING_INTEREST" if len(read_topic_slugs) <= 2 else "RELATED_TO_READING"

        # ---------------------------------------------------------------------
        # SOURCE 6: Trending within User's Interests (High Importance + Recent)
        # ---------------------------------------------------------------------
        stmt_trend = (
            select(Article)
            .join(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
            .where(
                Article.status == "PUBLISHED",
                Article.published_at >= recency_cutoff,
                ArticleAnalysis.importance_score >= 0.60,
            )
            .options(
                selectinload(Article.topics),
                selectinload(Article.analysis),
                selectinload(Article.entities),
                selectinload(Article.keywords),
            )
            .order_by(desc(ArticleAnalysis.importance_score), desc(Article.published_at))
            .limit(60)
        )
        res_trend = await self.session.execute(stmt_trend)
        for art in res_trend.scalars().all():
            if art.id not in candidate_map:
                candidate_map[art.id] = art
                reason_map[art.id] = "TRENDING_FOR_YOU"

        # ---------------------------------------------------------------------
        # SOURCE 1: Semantic / General Pool Backfill (up to target_pool_size)
        # ---------------------------------------------------------------------
        if len(candidate_map) < target_pool_size:
            remaining_needed = target_pool_size - len(candidate_map)
            stmt_gen = (
                select(Article)
                .where(Article.status == "PUBLISHED")
                .options(
                    selectinload(Article.topics),
                    selectinload(Article.analysis),
                    selectinload(Article.entities),
                    selectinload(Article.keywords),
                )
                .order_by(desc(Article.published_at))
                .limit(remaining_needed * 2)
            )
            res_gen = await self.session.execute(stmt_gen)
            for art in res_gen.scalars().all():
                if art.id not in candidate_map:
                    candidate_map[art.id] = art
                    reason_map[art.id] = "DISCOVERY"
                if len(candidate_map) >= target_pool_size:
                    break

        return list(candidate_map.values()), profile, reason_map
