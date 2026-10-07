"""change_detector.py — Phase 18 What's New & What Changed Detection."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.editorial.schemas import EditorialCandidate
from app.briefings.models import BriefingType

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class ChangeDetector:
    """
    Identifies what has genuinely changed since the user's last session:
    - NEW stories
    - UPDATED stories with meaningful developments
    - FOLLOW_UP stories to previously read items
    - IMPORTANT stories of broad public significance
    - FOR_YOU and DISCOVERY stories
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    def evaluate_candidate_change(
        self,
        candidate: EditorialCandidate,
        last_session_at: Optional[datetime],
        user_top_topics: Optional[List[str]] = None,
    ) -> Tuple[str, float, str]:
        """
        Determines the appropriate briefing_type, meaningful_update_score, and contextual explanation reason.

        Returns:
            (briefing_type, meaningful_update_score, explanation_reason)
        """
        now = utc_now()
        baseline_time = ensure_utc(last_session_at) or (now)
        pub_time = ensure_utc(candidate.published_at) or baseline_time

        user_topics = [t.lower() for t in (user_top_topics or [])]
        cand_topics_lower = [t.lower() for t in candidate.topics]
        is_topic_match = any(ut in cand_topics_lower or any(ut in ct for ct in cand_topics_lower) for ut in user_topics)

        # 1. Calculate Meaningful Update Score
        meaningful_update_score = self.calculate_meaningful_update_score(candidate)

        # 2. Check Read State & Updates (Follow-Up vs Updated)
        if candidate.is_read:
            if candidate.has_meaningful_update or meaningful_update_score >= 0.50:
                reason = "Follow-up: New updates since you last read this story."
                return BriefingType.FOLLOW_UP.value, meaningful_update_score, reason
            else:
                # Already read and unchanged — deprioritized
                reason = "You've already read this story."
                return BriefingType.FOR_YOU.value, 0.05, reason

        # 3. Check if Story was Updated after Last Session
        is_updated_after_session = False
        if candidate.story_id and candidate.story_article_count > 1:
            if meaningful_update_score >= 0.50:
                is_updated_after_session = True

        if is_updated_after_session:
            indep_count = getattr(candidate, "independent_source_count", candidate.source_count)
            reason = f"Story updated with new developments ({indep_count} independent sources)."
            return BriefingType.UPDATED.value, meaningful_update_score, reason

        # 4. Global Public Importance (breaking or high broad significance)
        if candidate.importance_score >= 0.85 or (candidate.importance_score >= 0.75 and candidate.source_count >= 3):
            if candidate.personal_relevance_score < 0.60:
                reason = "Major story with broad significance outside your usual topics."
            else:
                reason = "Major top development today."
            return BriefingType.IMPORTANT.value, meaningful_update_score, reason

        # 5. High Personal Relevance (For You)
        if candidate.personal_relevance_score >= 0.75 or (is_topic_match and candidate.personal_relevance_score >= 0.65):
            topic_name = candidate.topics[0] if candidate.topics else (candidate.primary_category or "News").title()
            reason = f"Because you frequently follow {topic_name}."
            return BriefingType.FOR_YOU.value, meaningful_update_score, reason

        # 6. Discovery Candidate
        if candidate.is_discovery_candidate or (candidate.novelty_score >= 0.70 and not is_topic_match):
            topic_name = candidate.topics[0] if candidate.topics else "this area"
            reason = f"New development in {topic_name}, related to your recent reading."
            return BriefingType.DISCOVERY.value, meaningful_update_score, reason

        # 7. Default: NEW story published recently
        if pub_time >= baseline_time:
            reason = "New development since your last visit."
        else:
            reason = "Essential story from today's news."

        return BriefingType.NEW.value, meaningful_update_score, reason

    def calculate_meaningful_update_score(self, candidate: EditorialCandidate) -> float:
        """
        Computes how meaningful recent developments are for a story.
        Prevents near-duplicate syndicated coverage from inflating updates.
        """
        score = 0.20  # baseline

        # Multi-source development
        indep_sources = getattr(candidate, "independent_source_count", 1)
        if indep_sources >= 3:
            score += 0.35
        elif indep_sources >= 2:
            score += 0.20

        # Developing flag from story intelligence
        if candidate.is_developing:
            score += 0.25

        # Quality bonus
        if candidate.quality_score >= 0.75:
            score += 0.15

        # High importance
        if candidate.importance_score >= 0.80:
            score += 0.15

        # Meaningful update flag from candidate selector
        if candidate.has_meaningful_update:
            score += 0.25

        return min(1.0, max(0.0, score))
