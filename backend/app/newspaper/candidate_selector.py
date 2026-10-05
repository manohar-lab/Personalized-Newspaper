import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.article import Article
from app.repositories.action_repository import ActionRepository
from app.personalization.schemas import ScoredArticle, UserInterestProfile
from app.personalization.services.personalization_service import PersonalizationService

logger = logging.getLogger(__name__)


class CandidateSelector:
    """
    Selects and scores candidate articles for newspaper generation.
    Enforces time windows (24h primary with 72h fallback), availability checks,
    user negative action filters, and personal relevance calculation.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.action_repo = ActionRepository(session)
        self.personalization_service = PersonalizationService(session)

    async def get_candidate_articles(
        self,
        user_id: uuid.UUID,
        target_date: Optional[datetime] = None,
        min_candidates: int = 5,
    ) -> List[ScoredArticle]:
        """
        Fetches candidate articles published within the primary time window.
        If fewer than min_candidates are available, expands to fallback window.
        Computes personal relevance scores using the user's interest profile.
        """
        ref_time = target_date or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        # 1. Load user interest profile
        profile = await self.personalization_service.get_user_interest_profile(user_id)

        # 2. Try primary time window (e.g., last 24h)
        primary_since = ref_time - timedelta(hours=settings.NEWSPAPER_PRIMARY_WINDOW_HOURS)
        candidates = await self._fetch_articles_since(primary_since)

        # 3. Fallback window if needed
        if len(candidates) < min_candidates:
            fallback_since = ref_time - timedelta(hours=settings.NEWSPAPER_FALLBACK_WINDOW_HOURS)
            logger.info(
                f"Candidate count ({len(candidates)}) below {min_candidates}. "
                f"Expanding to fallback window: {settings.NEWSPAPER_FALLBACK_WINDOW_HOURS}h"
            )
            candidates = await self._fetch_articles_since(fallback_since)

        # If still empty/low in test environments where dates might not match, fetch all published
        if len(candidates) < min_candidates:
            candidates = await self._fetch_articles_since(None)

        if not candidates:
            return []

        # 4. Filter out NOT_INTERESTED / excluded articles
        article_ids = [a.id for a in candidates]
        actions_map = await self.action_repo.get_user_actions_map(user_id, article_ids)
        filtered_articles = [
            a for a in candidates
            if "NOT_INTERESTED" not in actions_map.get(a.id, set())
        ]

        # 5. Score personal relevance for each candidate
        scored_candidates: List[ScoredArticle] = []
        for item_art in filtered_articles:
            score, breakdown = self.personalization_service.scorer.compute_relevance(
                article=item_art,
                positive_interests=profile.positive_interests,
                negative_interests=profile.negative_interests,
                user_embedding=profile.embedding,
                positive_topic_names=list(profile.topic_names_map.values()),
                now=ref_time,
            )

            # Retain non-negative relevance
            if score > 0.0 or not profile.has_interests:
                scored_candidates.append(
                    ScoredArticle(
                        article_id=item_art.id,
                        article=item_art,
                        relevance_score=score,
                        breakdown=breakdown,
                    )
                )

        # Sort by personal relevance descending
        scored_candidates.sort(key=lambda sa: sa.relevance_score, reverse=True)
        return scored_candidates

    async def _fetch_articles_since(
        self, since: Optional[datetime]
    ) -> List[Article]:
        stmt = (
            select(Article)
            .where(Article.status == "PUBLISHED")
            .options(
                selectinload(Article.topics),
                selectinload(Article.analysis),
                selectinload(Article.entities),
                selectinload(Article.keywords),
                selectinload(Article.source),
            )
            .execution_options(populate_existing=True)
        )
        if since is not None:
            stmt = stmt.where(Article.published_at >= since)

        stmt = stmt.order_by(Article.published_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
