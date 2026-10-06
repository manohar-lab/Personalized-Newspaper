"""candidate_filters.py — Candidate Filtering, Exclusion Rules, & Story Clustering."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.action import UserArticleAction
from app.models.reading_history import ReadingHistory
from app.recommendations.models import UserRecommendation
from app.newspaper.story_clusterer import StoryClusterer

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CandidateFilters:
    """Enforces exclusion rules, cooldowns, duplicate detection, and story clustering on candidate pools."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.clusterer = StoryClusterer(session=session)

    @staticmethod
    def _safe_get(obj: Any, attr: str, default=None):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        try:
            return getattr(obj, attr, default)
        except Exception:
            return default

    async def get_user_exclusion_ids(
        self,
        user_id: uuid.UUID,
        cooldown_hours: int = settings.RECOMMENDATION_COOLDOWN_HOURS,
    ) -> Dict[str, Set[uuid.UUID]]:
        """Fetch IDs of completed articles, NOT_INTERESTED articles, recently read articles, and cooldown recommendations."""
        now = utc_now()

        # 1. NOT_INTERESTED articles
        stmt_action = select(UserArticleAction.article_id).where(
            UserArticleAction.user_id == user_id,
            UserArticleAction.action == "NOT_INTERESTED",
        )
        res_action = await self.session.execute(stmt_action)
        not_interested_ids = set(res_action.scalars().all())

        # 2. Completed / Recently read articles
        stmt_read = select(ReadingHistory).where(ReadingHistory.user_id == user_id)
        res_read = await self.session.execute(stmt_read)
        read_records = list(res_read.scalars().all())

        completed_ids = set()
        recently_read_ids = set()
        cutoff_7d = now - timedelta(days=7)

        for r in read_records:
            if r.completion_count > 0 or r.last_completion_percentage >= settings.ARTICLE_COMPLETION_THRESHOLD:
                completed_ids.add(r.article_id)
            if r.last_read_at and r.last_read_at >= cutoff_7d:
                recently_read_ids.add(r.article_id)

        # 3. Recommendation Cooldown articles
        cooldown_cutoff = now - timedelta(hours=cooldown_hours)
        stmt_rec = select(UserRecommendation.article_id).where(
            UserRecommendation.user_id == user_id,
            UserRecommendation.recommended_at >= cooldown_cutoff,
        )
        res_rec = await self.session.execute(stmt_rec)
        cooldown_ids = set(res_rec.scalars().all())

        # 4. Muted sources
        from app.source_intelligence.models import UserSourcePreference
        stmt_muted = select(UserSourcePreference.source_id).where(
            UserSourcePreference.user_id == user_id,
            UserSourcePreference.is_muted == True,
        )
        res_muted = await self.session.execute(stmt_muted)
        muted_source_ids = set(res_muted.scalars().all())

        return {
            "not_interested": not_interested_ids,
            "completed": completed_ids,
            "recently_read": recently_read_ids,
            "cooldown": cooldown_ids,
            "muted_sources": muted_source_ids,
        }

    async def filter_candidates(
        self,
        user_id: uuid.UUID,
        candidates: List[Any],
        exclude_cooldown: bool = True,
        exclude_read: bool = True,
    ) -> List[Any]:
        """Apply strict exclusion filters for ineligible or duplicate candidate articles."""
        if not candidates:
            return []

        exclusions = await self.get_user_exclusion_ids(user_id)
        not_interested = exclusions["not_interested"]
        completed = exclusions["completed"]
        recently_read = exclusions["recently_read"]
        cooldown = exclusions["cooldown"]
        muted_sources = exclusions["muted_sources"]

        seen_ids: Set[uuid.UUID] = set()
        seen_titles: Set[str] = set()
        seen_urls: Set[str] = set()
        valid_candidates: List[Any] = []

        for art in candidates:
            art_id = self._safe_get(art, "id")
            if not art_id or art_id in seen_ids:
                continue

            # 1. Status & extraction check
            status = self._safe_get(art, "status", "PUBLISHED")
            ext_status = self._safe_get(art, "extraction_status", "COMPLETED")
            if status != "PUBLISHED" or ext_status == "FAILED":
                continue

            # 2. NOT_INTERESTED check
            if art_id in not_interested:
                continue

            # 3. Completed check
            if exclude_read and art_id in completed:
                continue

            # 4. Recently read check (exclude unless part of candidate pool overrides)
            if exclude_read and art_id in recently_read:
                continue

            # 5. Cooldown check
            if exclude_cooldown and art_id in cooldown:
                continue

            # 5b. Muted source check
            src_id = self._safe_get(art, "source_id")
            if src_id and src_id in muted_sources:
                continue

            # 6. Title / Canonical URL deduplication
            title = (self._safe_get(art, "title") or "").strip().lower()
            canon_url = (self._safe_get(art, "canonical_url") or self._safe_get(art, "source_url") or "").strip().lower()

            if title and title in seen_titles:
                continue
            if canon_url and canon_url in seen_urls:
                continue

            seen_ids.add(art_id)
            if title:
                seen_titles.add(title)
            if canon_url:
                seen_urls.add(canon_url)

            valid_candidates.append(art)

        return valid_candidates

    async def apply_story_clustering(self, candidates: List[Any]) -> List[Any]:
        """Reuse Phase 9 StoryClusterer to group multi-source coverage of same story and elect 1 primary article."""
        if not candidates or len(candidates) <= 1:
            return candidates

        # Wrap candidates into temporary ScoredArticle format expected by StoryClusterer
        from app.personalization.schemas import ScoredArticle, RelevanceScoreBreakdown
        scored_wrappers = []
        for art in candidates:
            wrapper = ScoredArticle(
                article_id=art.id,
                article=art,
                relevance_score=0.5,
                breakdown=RelevanceScoreBreakdown(final_score=0.5),
            )
            scored_wrappers.append(wrapper)

        primary_wrappers, _ = await self.clusterer.cluster_and_elect_primary(scored_wrappers)
        return [w.article for w in primary_wrappers]
