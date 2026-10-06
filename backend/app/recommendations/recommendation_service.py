"""recommendation_service.py — Primary Recommendation Service Orchestrator."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.article import Article
from app.models.reading_history import ReadingHistory
from app.models.user import User
from app.recommendations.models import UserRecommendation
from app.recommendations.schemas import (
    RecommendationItem,
    RecommendationFeedResponse,
    TrendingForYouResponse,
    MoreLikeThisResponse,
)
from app.recommendations.candidate_generator import CandidateGenerator
from app.recommendations.candidate_filters import CandidateFilters
from app.recommendations.scoring import RecommendationScorer
from app.recommendations.diversity import RecommendationDiversityEngine
from app.recommendations.explanations import ExplanationGenerator
from app.learning.agent import InterestLearningAgent

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RecommendationService:
    """Primary recommendation engine service orchestrating candidate generation, scoring, diversity, and caching."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.candidate_generator = CandidateGenerator(session)
        self.candidate_filters = CandidateFilters(session)
        self.scorer = RecommendationScorer()
        self.diversity_engine = RecommendationDiversityEngine()
        self.explanation_generator = ExplanationGenerator()
        self.learning_agent = InterestLearningAgent(session)

    @staticmethod
    def _safe_get(obj: Any, attr: str, default=None):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        try:
            return getattr(obj, attr, default)
        except Exception:
            return default

    async def recommend(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
        context: Optional[str] = "DISCOVER",
        page: int = 1,
        force_refresh: bool = False,
    ) -> RecommendationFeedResponse:
        """Main service entry point returning personalized recommendation feed for user."""
        ctx = (context or "DISCOVER").upper().strip()
        now = utc_now()

        # ---------------------------------------------------------------------
        # 1. Check Short-Lived Cache / Persisted Recommendation Batch
        # ---------------------------------------------------------------------
        cache_ttl = timedelta(minutes=settings.RECOMMENDATION_CACHE_TTL_MINUTES)
        cache_cutoff = now - cache_ttl

        if not force_refresh:
            stmt_cache = (
                select(UserRecommendation)
                .options(
                    selectinload(UserRecommendation.article).selectinload(Article.topics),
                    selectinload(UserRecommendation.article).selectinload(Article.analysis),
                    selectinload(UserRecommendation.article).selectinload(Article.entities),
                )
                .where(
                    UserRecommendation.user_id == user_id,
                    UserRecommendation.context == ctx,
                    UserRecommendation.recommended_at >= cache_cutoff,
                )
                .order_by(desc(UserRecommendation.recommendation_score))
            )
            res_cache = await self.session.execute(stmt_cache)
            cached_recs = list(res_cache.scalars().all())

            if len(cached_recs) >= limit:
                logger.info(f"Serving {len(cached_recs)} cached recommendations for user {user_id}")
                items = await self._build_recommendation_items_from_models(user_id, cached_recs)
                return self._build_feed_response(items, page=page, limit=limit, context=ctx)

        # ---------------------------------------------------------------------
        # 2. Candidate Generation (100–300 candidates)
        # ---------------------------------------------------------------------
        candidates, profile, source_reasons = await self.candidate_generator.generate_candidates(
            user_id=user_id,
            target_pool_size=200,
        )

        # ---------------------------------------------------------------------
        # 3. Candidate Exclusion Filters & Story Clustering
        # ---------------------------------------------------------------------
        filtered_candidates = await self.candidate_filters.filter_candidates(
            user_id=user_id,
            candidates=candidates,
            exclude_cooldown=True,
            exclude_read=True,
        )

        # Apply Story Clustering (reuse Phase 9 StoryClusterer)
        clustered_candidates = await self.candidate_filters.apply_story_clustering(filtered_candidates)

        if not clustered_candidates:
            # Graceful Fallback if filters removed everything: retry without cooldown filter
            clustered_candidates = await self.candidate_filters.filter_candidates(
                user_id=user_id,
                candidates=candidates,
                exclude_cooldown=False,
                exclude_read=False,
            )

        # ---------------------------------------------------------------------
        # 4. Centralized Recommendation Scoring
        # ---------------------------------------------------------------------
        exclusions = await self.candidate_filters.get_user_exclusion_ids(user_id)
        cooldown_ids = exclusions["cooldown"]

        # Fetch recently read embeddings for novelty scoring
        stmt_read_emb = (
            select(ReadingHistory)
            .options(selectinload(ReadingHistory.article).selectinload(Article.analysis))
            .where(ReadingHistory.user_id == user_id)
            .order_by(desc(ReadingHistory.last_read_at))
            .limit(10)
        )
        res_read_emb = await self.session.execute(stmt_read_emb)
        read_embs = []
        for r in res_read_emb.scalars().all():
            if r.article and r.article.analysis and r.article.analysis.embedding:
                read_embs.append(r.article.analysis.embedding)

        scored_list: List[Tuple[Article, float, Dict[str, Any]]] = []
        for art in clustered_candidates:
            reason = source_reasons.get(art.id, "STRONG_INTEREST")
            is_emerging = (reason == "EMERGING_INTEREST")

            score, breakdown = self.scorer.compute_score(
                article=art,
                positive_interests=profile.positive_interests,
                negative_interests=profile.negative_interests,
                user_embedding=profile.embedding,
                learned_entities=profile.learned_entities,
                recently_read_embeddings=read_embs,
                recently_recommended_ids=cooldown_ids,
                is_emerging=is_emerging,
                now=now,
            )
            breakdown["source_reason"] = reason
            scored_list.append((art, score, breakdown))

        # ---------------------------------------------------------------------
        # 5. Diversity Engine & Exploration/Exploitation Split
        # ---------------------------------------------------------------------
        top_topic = list(profile.positive_interests.keys())[0] if profile.positive_interests else None
        final_selected = self.diversity_engine.apply_diversity_and_exploration(
            scored_candidates=scored_list,
            limit=limit,
            top_dominant_topic=top_topic,
        )

        # ---------------------------------------------------------------------
        # 6. Explanations & Database Batch Persistence
        # ---------------------------------------------------------------------
        rec_models: List[UserRecommendation] = []
        items: List[RecommendationItem] = []

        # Delete expired or stale cache records for user + context
        await self.session.execute(
            delete(UserRecommendation).where(
                UserRecommendation.user_id == user_id,
                UserRecommendation.context == ctx,
            )
        )

        for art, score, breakdown in final_selected:
            reason_type = breakdown.get("source_reason", "STRONG_INTEREST")
            if breakdown.get("is_exploration"):
                reason_type = "DISCOVERY"

            primary_topic_name = art.topics[0].name if art.topics else None
            primary_entity_name = art.entities[0].name if art.entities else None

            exp = self.explanation_generator.generate_explanation(
                reason_type=reason_type,
                topic_name=primary_topic_name,
                entity_name=primary_entity_name,
            )

            # Determine section grouping
            section = "Recommended for you"
            if exp["reason_type"] == "DISCOVERY":
                section = "Discover something new"
            elif exp["reason_type"] == "TRENDING_FOR_YOU":
                section = "Trending in your interests"

            rec_model = UserRecommendation(
                id=uuid.uuid4(),
                user_id=user_id,
                article_id=art.id,
                context=ctx,
                recommendation_score=score,
                reason_type=exp["reason_type"],
                reason_text=exp["reason_text"],
                section=section,
                is_shown=False,
                is_clicked=False,
                recommended_at=now,
                expires_at=now + cache_ttl,
            )
            self.session.add(rec_model)
            rec_models.append(rec_model)

            reading_min = art.reading_time_minutes or max(1, len((art.content or "").split()) // 200)

            items.append(
                RecommendationItem(
                    article_id=art.id,
                    title=art.title,
                    summary=art.description or (art.content[:200] if art.content else ""),
                    source=art.source_name,
                    published_at=art.published_at,
                    image=art.image_url,
                    reading_time=reading_min,
                    recommendation_score_hidden=score,
                    reason_type=exp["reason_type"],
                    reason_text=exp["reason_text"],
                    section=section,
                    is_new=True,
                    is_read=False,
                )
            )

        await self.session.commit()
        return self._build_feed_response(items, page=page, limit=limit, context=ctx)

    async def _build_recommendation_items_from_models(
        self,
        user_id: uuid.UUID,
        rec_models: List[UserRecommendation],
    ) -> List[RecommendationItem]:
        """Convert database recommendation rows into RecommendationItem response objects."""
        exclusions = await self.candidate_filters.get_user_exclusion_ids(user_id)
        completed_ids = exclusions["completed"]

        items: List[RecommendationItem] = []
        for rm in rec_models:
            art = rm.article
            if not art:
                continue
            reading_min = art.reading_time_minutes or max(1, len((art.content or "").split()) // 200)
            items.append(
                RecommendationItem(
                    article_id=art.id,
                    title=art.title,
                    summary=art.description or (art.content[:200] if art.content else ""),
                    source=art.source_name,
                    published_at=art.published_at,
                    image=art.image_url,
                    reading_time=reading_min,
                    recommendation_score_hidden=rm.recommendation_score,
                    reason_type=rm.reason_type,
                    reason_text=rm.reason_text,
                    section=rm.section or "Recommended for you",
                    is_new=not rm.is_shown,
                    is_read=art.id in completed_ids,
                )
            )
        return items

    def _build_feed_response(
        self,
        items: List[RecommendationItem],
        page: int = 1,
        limit: int = 20,
        context: str = "DISCOVER",
    ) -> RecommendationFeedResponse:
        """Structure output items into unified feed and section categories."""
        start_idx = (page - 1) * limit
        paginated_items = items[start_idx : start_idx + limit]

        rec_for_you = [i for i in paginated_items if i.section == "Recommended for you"]
        trending = [i for i in paginated_items if i.section == "Trending in your interests"]
        discover_new = [i for i in paginated_items if i.section == "Discover something new"]

        # Fallback to recommended_for_you if sectioning is empty
        if not rec_for_you and paginated_items:
            rec_for_you = paginated_items

        return RecommendationFeedResponse(
            total=len(items),
            page=page,
            limit=limit,
            context=context,
            recommendations=paginated_items,
            recommended_for_you=rec_for_you,
            trending_in_your_interests=trending,
            discover_something_new=discover_new,
        )

    async def get_trending_for_you(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> TrendingForYouResponse:
        """Find important stories among user's preferred topics (global importance x user relevance x recency)."""
        feed = await self.recommend(user_id=user_id, limit=30, context="TRENDING")
        trending_items = [i for i in feed.recommendations if i.recommendation_score_hidden >= 0.40]
        if not trending_items:
            trending_items = feed.recommendations

        return TrendingForYouResponse(
            total=len(trending_items[:limit]),
            recommendations=trending_items[:limit],
        )

    async def get_more_like_this(
        self,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
        limit: int = 6,
    ) -> MoreLikeThisResponse:
        """Generate 'More like this' recommendations based on target article embedding & topic overlap."""
        stmt_target = (
            select(Article)
            .options(
                selectinload(Article.topics),
                selectinload(Article.analysis),
                selectinload(Article.entities),
            )
            .where(Article.id == article_id)
        )
        res_target = await self.session.execute(stmt_target)
        target_art = res_target.scalar_one_or_none()

        if not target_art:
            return MoreLikeThisResponse(article_id=article_id, recommendations=[])

        target_emb = target_art.analysis.embedding if target_art.analysis else None
        target_topic_slugs = [t.slug for t in target_art.topics]

        # Query candidate articles with matching topics
        stmt_cand = (
            select(Article)
            .where(
                Article.status == "PUBLISHED",
                Article.id != article_id,
            )
            .options(
                selectinload(Article.topics),
                selectinload(Article.analysis),
            )
            .order_by(desc(Article.published_at))
            .limit(50)
        )
        res_cand = await self.session.execute(stmt_cand)
        candidates = list(res_cand.scalars().all())

        scored_candidates: List[Tuple[Article, float]] = []
        for cand in candidates:
            sim = 0.0
            if target_emb and cand.analysis and cand.analysis.embedding:
                from app.personalization.scoring.semantic_scorer import SemanticScorer
                sim = SemanticScorer.cosine_similarity(target_emb, cand.analysis.embedding)

            # Topic overlap boost
            cand_topic_slugs = [t.slug for t in cand.topics]
            overlap = len(set(target_topic_slugs) & set(cand_topic_slugs))
            score = sim * 0.70 + (overlap * 0.15)
            scored_candidates.append((cand, score))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        items: List[RecommendationItem] = []
        for art, score in scored_candidates[:limit]:
            exp = self.explanation_generator.generate_explanation(
                reason_type="SIMILAR_ARTICLE",
                source_article_title=target_art.title,
            )
            reading_min = art.reading_time_minutes or max(1, len((art.content or "").split()) // 200)

            items.append(
                RecommendationItem(
                    article_id=art.id,
                    title=art.title,
                    summary=art.description or (art.content[:200] if art.content else ""),
                    source=art.source_name,
                    published_at=art.published_at,
                    image=art.image_url,
                    reading_time=reading_min,
                    recommendation_score_hidden=round(score, 4),
                    reason_type=exp["reason_type"],
                    reason_text=exp["reason_text"],
                    section="More like this",
                    is_new=True,
                    is_read=False,
                )
            )

        return MoreLikeThisResponse(article_id=article_id, recommendations=items)

    async def record_interaction(
        self,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
        interaction_type: str,
        context: Optional[str] = "DISCOVER",
    ) -> None:
        """Record recommendation impression or click, and update learning agent pipeline."""
        itype = interaction_type.upper().strip()
        now = utc_now()

        # Update UserRecommendation row
        stmt_rec = select(UserRecommendation).where(
            UserRecommendation.user_id == user_id,
            UserRecommendation.article_id == article_id,
        )
        res_rec = await self.session.execute(stmt_rec)
        rec_model = res_rec.scalar_one_or_none()

        if rec_model:
            if itype == "IMPRESSION":
                rec_model.is_shown = True
                rec_model.shown_at = now
            elif itype == "CLICK":
                rec_model.is_clicked = True
                rec_model.clicked_at = now

        # Integrate with behavior / learning pipeline (Phase 13 agent)
        event_type = "ARTICLE_IMPRESSION" if itype == "IMPRESSION" else "ARTICLE_OPEN"
        val = 0.0 if itype == "IMPRESSION" else 0.5

        await self.learning_agent.process_event(
            user_id=user_id,
            event_type=event_type,
            article_id=article_id,
            value=val,
            metadata={"source": "RECOMMENDATION", "context": context},
            commit=True,
        )
