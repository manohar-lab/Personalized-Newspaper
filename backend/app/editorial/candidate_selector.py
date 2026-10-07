"""candidate_selector.py — Phase 17 Multi-Source Editorial Candidate Pool Builder & Filter."""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.models.reading_history import ReadingHistory
from app.models.source import NewsSource
from app.story_intelligence.models import Story, StoryArticle
from app.source_intelligence.models import UserSourcePreference
from app.recommendations.recommendation_service import RecommendationService
from app.ai.interests.learner import InterestLearningService
from app.personalization.services.personalization_service import PersonalizationService
from app.editorial.schemas import EditorialCandidate

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime is timezone-aware UTC, even if returned naive from SQLite."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class EditorialCandidateSelector:
    """Builds and filters the rich editorial candidate pool for a user's daily newspaper."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.personalization_service = PersonalizationService(session)
        self.recommendation_service = RecommendationService(session)
        self.interest_service = InterestLearningService(session)

    async def get_candidate_pool(
        self,
        user_id: uuid.UUID,
        target_date: Optional[datetime] = None,
        lookback_hours: int = 72,
        min_quality_threshold: float = 0.20,
    ) -> Tuple[List[EditorialCandidate], List[Dict[str, str]]]:
        """
        Collects candidates from stories, recent articles, recommendations, and followed sources,
        applies editorial quality filters, deduplication, and read-awareness.
        
        Returns:
            (valid_candidates, exclusion_audit_log)
        """
        now = ensure_utc(target_date) or utc_now()
        since_time = now - timedelta(hours=lookback_hours)
        exclusion_log: List[Dict[str, str]] = []

        # 1. Fetch user preferences & muted sources
        muted_source_ids = await self._get_muted_source_ids(user_id)
        followed_source_ids = await self._get_followed_source_ids(user_id)

        # 2. Fetch user dynamic interests & strong/emerging topics
        strong_topic_slugs = set()
        emerging_topic_slugs = set()
        try:
            profile = await self.interest_service.get_dynamic_profile(user_id)
            if profile:
                strong_topic_slugs = {item.slug for item in (getattr(profile, "strong_interests", []) + getattr(profile, "explicit_interests", []))}
                emerging_topic_slugs = {item.slug for item in getattr(profile, "emerging_interests", [])}
        except Exception as e:
            logger.debug(f"Dynamic profile fetch note: {e}")

        # 3. Fetch user reading history
        reading_map = await self._get_user_reading_history(user_id)

        # 4. Fetch Multi-Source Stories (Phase 16)
        stories_stmt = (
            select(Story)
            .options(
                selectinload(Story.primary_article).selectinload(Article.analysis),
                selectinload(Story.primary_article).selectinload(Article.topics),
                selectinload(Story.primary_article).selectinload(Article.entities),
                selectinload(Story.latest_article).selectinload(Article.analysis),
                selectinload(Story.latest_article).selectinload(Article.topics),
                selectinload(Story.story_articles).selectinload(StoryArticle.article).selectinload(Article.analysis),
                selectinload(Story.primary_topic),
            )
            .where(
                Story.merged_into_story_id == None,
                Story.last_updated_at >= since_time,
                Story.status.in_(["ACTIVE", "DEVELOPING", "STABLE"]),
            )
            .order_by(Story.importance_score.desc(), Story.last_updated_at.desc())
            .limit(100)
        )
        stories_res = await self.session.execute(stories_stmt)
        stories = list(stories_res.scalars().all())

        # 5. Fetch Standalone Published Articles (to ensure broad coverage)
        articles_stmt = (
            select(Article)
            .options(
                selectinload(Article.analysis),
                selectinload(Article.topics),
                selectinload(Article.entities),
                selectinload(Article.source),
            )
            .where(
                Article.status == "PUBLISHED",
                Article.published_at >= since_time,
            )
            .order_by(Article.published_at.desc())
            .limit(150)
        )
        articles_res = await self.session.execute(articles_stmt)
        articles = list(articles_res.scalars().all())

        # Also get recommendations (Phase 14)
        rec_article_ids: Set[uuid.UUID] = set()
        try:
            recs = await self.recommendation_service.recommend(
                user_id=user_id, limit=20, context="FOR_YOU"
            )
            for r in recs.recommendations:
                rec_article_ids.add(uuid.UUID(r.article_id))
        except Exception as e:
            logger.debug(f"Recommendations fetch note: {e}")

        # Map story articles to prevent duplicate standalone inclusion
        story_article_ids: Set[uuid.UUID] = set()
        for st in stories:
            if st.primary_article_id:
                story_article_ids.add(st.primary_article_id)
            if st.latest_article_id:
                story_article_ids.add(st.latest_article_id)
            for sa in st.story_articles:
                story_article_ids.add(sa.article_id)

        candidates: List[EditorialCandidate] = []
        seen_titles: Set[str] = set()

        # 6. Convert Stories into Candidates (Preferred)
        for st in stories:
            primary_art = st.primary_article or (st.story_articles[0].article if st.story_articles else None)
            if not primary_art:
                exclusion_log.append({"item_id": str(st.id), "title": st.title, "reason": "Story has no valid primary article"})
                continue

            # Muted source check
            if primary_art.source_id and primary_art.source_id in muted_source_ids:
                exclusion_log.append({"item_id": str(st.id), "title": st.title, "reason": "Muted source"})
                continue

            # Quality filter
            effective_quality = max(
                st.quality_score,
                getattr(primary_art.analysis, "article_quality_score", 0.5) if primary_art.analysis else 0.5,
            )
            if effective_quality < min_quality_threshold:
                exclusion_log.append({"item_id": str(st.id), "title": st.title, "reason": f"Low quality score: {effective_quality:.2f}"})
                continue

            # Content completeness
            content_text = primary_art.content or primary_art.description or ""
            if len(content_text.strip()) < 40 and not primary_art.is_full_text_available:
                exclusion_log.append({"item_id": str(st.id), "title": st.title, "reason": "No meaningful content"})
                continue

            # Title normalization deduplication
            norm_title = " ".join(st.title.lower().split()[:6])
            if norm_title in seen_titles:
                exclusion_log.append({"item_id": str(st.id), "title": st.title, "reason": "Duplicate story coverage"})
                continue
            seen_titles.add(norm_title)

            # Read-Awareness
            read_info = reading_map.get(primary_art.id)
            is_read = False
            read_pct = 0.0
            has_meaningful_update = False

            st_updated = ensure_utc(st.last_updated_at) or now
            if read_info:
                read_pct = read_info.get("completion_pct", 0.0)
                is_read = read_pct >= 0.8 or read_info.get("is_completed", False)
                # Check if story has updates after user's last read
                last_read_dt = ensure_utc(read_info.get("last_read_at"))
                if last_read_dt and st_updated > last_read_dt:
                    has_meaningful_update = True

            # Extract topics and entities
            cand_topics = [t.name for t in primary_art.topics] if primary_art.topics else []
            if st.primary_topic and st.primary_topic.name not in cand_topics:
                cand_topics.append(st.primary_topic.name)
            cand_entities = [e.name for e in primary_art.entities] if primary_art.entities else []

            # Personal relevance scoring
            rel_score = await self._calculate_personal_relevance(user_id, primary_art)
            if primary_art.id in rec_article_ids:
                rel_score = min(1.0, rel_score + 0.10)

            # User affinity (followed sources, high engagement)
            user_affinity = 0.15 if (primary_art.source_id and primary_art.source_id in followed_source_ids) else 0.0

            # Recency score calculation (exponential decay)
            age_hours = max(0.1, (now - st_updated).total_seconds() / 3600.0)
            recency = max(0.1, 1.0 / (1.0 + 0.05 * age_hours))

            # Public Importance Bonus (breaking/developing or high importance)
            pub_bonus = 0.0
            if st.importance_score >= 0.80 or st.source_count >= 3:
                pub_bonus = min(0.25, 0.10 + 0.05 * (st.source_count - 1))

            # Novelty / Discovery candidate
            is_discovery = any(t.lower() in [s.lower() for s in emerging_topic_slugs] for t in cand_topics)

            cand = EditorialCandidate(
                story_id=st.id,
                article_id=primary_art.id,
                title=st.title,
                summary=st.summary or (primary_art.analysis.summary if primary_art.analysis else primary_art.description),
                content=primary_art.content,
                url=primary_art.canonical_url or primary_art.source_url,
                top_image_url=primary_art.image_url,
                source_name=primary_art.source.name if primary_art.source else "News Wire",
                source_id=primary_art.source_id,
                published_at=st.first_published_at,
                reading_time_minutes=primary_art.reading_time_minutes or 3,
                primary_category=primary_art.analysis.primary_category if primary_art.analysis else "GENERAL",
                topics=cand_topics,
                entities=cand_entities,
                embedding=primary_art.analysis.embedding if primary_art.analysis else None,
                importance_score=st.importance_score,
                quality_score=effective_quality,
                activity_score=st.activity_score,
                source_count=st.source_count,
                independent_source_count=st.independent_source_count,
                is_developing=(st.status == "DEVELOPING"),
                is_breaking=(st.importance_score >= 0.85),
                is_syndicated=False,
                personal_relevance_score=rel_score,
                user_affinity_score=user_affinity,
                recency_score=recency,
                novelty_score=0.8 if is_discovery else 0.5,
                public_importance_bonus=pub_bonus,
                is_read=is_read,
                user_read_percentage=read_pct,
                has_meaningful_update=has_meaningful_update,
                story_slug=st.slug,
                story_article_count=st.article_count,
                story_source_count=st.source_count,
                is_discovery_candidate=is_discovery,
            )
            candidates.append(cand)

        # 7. Convert standalone articles not already covered by a story
        for art in articles:
            if art.id in story_article_ids:
                continue

            if art.source_id and art.source_id in muted_source_ids:
                exclusion_log.append({"item_id": str(art.id), "title": art.title, "reason": "Muted source"})
                continue

            art_quality = (
                getattr(art.analysis, "article_quality_score", 0.5) if art.analysis else 0.5
            )
            if art_quality < min_quality_threshold:
                exclusion_log.append({"item_id": str(art.id), "title": art.title, "reason": f"Low quality score: {art_quality:.2f}"})
                continue

            content_text = art.content or art.description or ""
            if len(content_text.strip()) < 40 and not art.is_full_text_available:
                exclusion_log.append({"item_id": str(art.id), "title": art.title, "reason": "No meaningful content"})
                continue

            norm_title = " ".join(art.title.lower().split()[:6])
            if norm_title in seen_titles:
                exclusion_log.append({"item_id": str(art.id), "title": art.title, "reason": "Duplicate article coverage"})
                continue
            seen_titles.add(norm_title)

            # Read-Awareness
            read_info = reading_map.get(art.id)
            is_read = False
            read_pct = 0.0
            if read_info:
                read_pct = read_info.get("completion_pct", 0.0)
                is_read = read_pct >= 0.8 or read_info.get("is_completed", False)

            cand_topics = [t.name for t in art.topics] if art.topics else []
            cand_entities = [e.name for e in art.entities] if art.entities else []
            rel_score = await self._calculate_personal_relevance(user_id, art)
            if art.id in rec_article_ids:
                rel_score = min(1.0, rel_score + 0.10)

            user_affinity = 0.15 if (art.source_id and art.source_id in followed_source_ids) else 0.0
            pub_time = ensure_utc(art.published_at) or now
            age_hours = max(0.1, (now - pub_time).total_seconds() / 3600.0)
            recency = max(0.1, 1.0 / (1.0 + 0.05 * age_hours))

            importance = art.analysis.importance_score if art.analysis else 0.5
            pub_bonus = 0.15 if importance >= 0.85 else 0.0
            is_discovery = any(t.lower() in [s.lower() for s in emerging_topic_slugs] for t in cand_topics)

            cand = EditorialCandidate(
                story_id=None,
                article_id=art.id,
                title=art.title,
                summary=art.analysis.summary if art.analysis else art.description,
                content=art.content,
                url=art.canonical_url or art.source_url,
                top_image_url=art.image_url,
                source_name=art.source.name if art.source else "Independent Source",
                source_id=art.source_id,
                published_at=art.published_at,
                reading_time_minutes=art.reading_time_minutes or 3,
                primary_category=art.analysis.primary_category if art.analysis else "GENERAL",
                topics=cand_topics,
                entities=cand_entities,
                embedding=art.analysis.embedding if art.analysis else None,
                importance_score=importance,
                quality_score=art_quality,
                activity_score=0.4,
                source_count=1,
                independent_source_count=1,
                is_developing=False,
                is_breaking=importance >= 0.85,
                is_syndicated=False,
                personal_relevance_score=rel_score,
                user_affinity_score=user_affinity,
                recency_score=recency,
                novelty_score=0.8 if is_discovery else 0.5,
                public_importance_bonus=pub_bonus,
                is_read=is_read,
                user_read_percentage=read_pct,
                has_meaningful_update=False,
                is_discovery_candidate=is_discovery,
            )
            candidates.append(cand)

        return candidates, exclusion_log

    async def _get_muted_source_ids(self, user_id: uuid.UUID) -> Set[uuid.UUID]:
        stmt = select(UserSourcePreference.source_id).where(
            UserSourcePreference.user_id == user_id,
            UserSourcePreference.is_muted == True,
        )
        res = await self.session.execute(stmt)
        return set(res.scalars().all())

    async def _get_followed_source_ids(self, user_id: uuid.UUID) -> Set[uuid.UUID]:
        stmt = select(UserSourcePreference.source_id).where(
            UserSourcePreference.user_id == user_id,
            UserSourcePreference.is_following == True,
        )
        res = await self.session.execute(stmt)
        return set(res.scalars().all())

    async def _get_user_reading_history(self, user_id: uuid.UUID) -> Dict[uuid.UUID, Dict[str, Any]]:
        stmt = select(ReadingHistory).where(ReadingHistory.user_id == user_id)
        res = await self.session.execute(stmt)
        records = list(res.scalars().all())
        history: Dict[uuid.UUID, Dict[str, Any]] = {}
        for r in records:
            history[r.article_id] = {
                "completion_pct": r.last_completion_percentage,
                "is_completed": r.completion_count > 0,
                "last_read_at": r.last_read_at,
            }
        return history

    async def _calculate_personal_relevance(self, user_id: uuid.UUID, article: Article) -> float:
        try:
            score, breakdown = await self.personalization_service.calculate_article_relevance(
                user_id=user_id, article_id=article.id
            )
            return float(score)
        except Exception as e:
            logger.debug(f"Relevance calculation note for article {article.id}: {e}")
            return 0.5
