"""briefing_selector.py — Phase 18 Editorial Selection for Daily Briefings."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.editorial.schemas import EditorialCandidate
from app.briefings.models import BriefingType, Daypart
from app.briefings.change_detector import ChangeDetector

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BriefingCandidate:
    """Internal container for evaluated briefing candidate."""
    def __init__(
        self,
        candidate: EditorialCandidate,
        briefing_type: str,
        meaningful_update_score: float,
        reason: str,
        briefing_score: float,
    ):
        self.candidate = candidate
        self.briefing_type = briefing_type
        self.meaningful_update_score = meaningful_update_score
        self.reason = reason
        self.briefing_score = briefing_score


class BriefingSelector:
    """Selects, ranks, and composes 3–7 diverse, personalized briefing items."""

    def __init__(self, change_detector: ChangeDetector):
        self.change_detector = change_detector

    def select_briefing_items(
        self,
        candidates: List[EditorialCandidate],
        last_session_at: Optional[datetime],
        user_top_topics: Optional[List[str]] = None,
        max_items: int = 7,
        min_items: int = 3,
        daypart: str = Daypart.MORNING.value,
    ) -> Tuple[List[BriefingCandidate], List[BriefingCandidate], List[BriefingCandidate], bool, str]:
        """
        Ranks and balances candidates into a crisp briefing.

        Returns:
            (top_items, what_changed, all_items, is_caught_up, intro_text)
        """
        evaluated: List[BriefingCandidate] = []
        user_topics = user_top_topics or []

        # 1. Evaluate change detection & compute briefing score
        for cand in candidates:
            b_type, update_score, reason = self.change_detector.evaluate_candidate_change(
                cand, last_session_at, user_topics
            )

            # Global public importance boost for major events of broad significance
            public_importance_boost = 0.0
            if cand.importance_score >= 0.85 or b_type == BriefingType.IMPORTANT.value:
                public_importance_boost = 0.18

            # Centralized briefing score
            b_score = (
                0.30 * cand.personal_relevance_score
                + 0.25 * cand.importance_score
                + 0.15 * cand.recency_score
                + 0.15 * update_score
                + 0.10 * cand.activity_score
                + 0.05 * cand.novelty_score
                + public_importance_boost
            )

            # Read penalty if user read and no updates
            if cand.is_read and not cand.has_meaningful_update and update_score < 0.40:
                b_score -= 0.45

            evaluated.append(
                BriefingCandidate(
                    candidate=cand,
                    briefing_type=b_type,
                    meaningful_update_score=update_score,
                    reason=reason,
                    briefing_score=max(0.0, min(1.0, b_score)),
                )
            )

        # Sort candidates by briefing score descending
        evaluated.sort(key=lambda x: x.briefing_score, reverse=True)

        # 2. Check for "Caught Up" condition
        # If all candidates are read or have no new/meaningful updates
        unread_or_new = [
            b for b in evaluated
            if (not b.candidate.is_read) or (b.candidate.has_meaningful_update and b.meaningful_update_score >= 0.40)
        ]

        if not unread_or_new and len(evaluated) > 0:
            is_caught_up = True
            intro = "You're all caught up! No major new developments since your last visit."
            return [], [], [], is_caught_up, intro

        is_caught_up = False

        # 3. Apply Diversity & Deduplication Filters
        selected: List[BriefingCandidate] = []
        seen_story_ids: Set[Any] = set()
        seen_titles: Set[str] = set()
        topic_counts: Dict[str, int] = {}
        source_counts: Dict[str, int] = {}

        for b in evaluated:
            if len(selected) >= max_items:
                break

            cand = b.candidate

            # Story-level deduplication
            if cand.story_id and cand.story_id in seen_story_ids:
                continue
            norm_title = " ".join(cand.title.lower().split()[:5])
            if norm_title in seen_titles:
                continue

            # Diversity limits
            first_topic = (cand.topics[0] if cand.topics else cand.primary_category or "GENERAL").lower()
            if topic_counts.get(first_topic, 0) >= 2 and len(evaluated) > 5:
                # Allow only if score is exceptionally high
                if b.briefing_score < 0.85:
                    continue

            src_key = cand.source_name.lower() if cand.source_name else "wire"
            if source_counts.get(src_key, 0) >= 2 and len(evaluated) > 5:
                continue

            # Accept item
            if cand.story_id:
                seen_story_ids.add(cand.story_id)
            seen_titles.add(norm_title)
            topic_counts[first_topic] = topic_counts.get(first_topic, 0) + 1
            source_counts[src_key] = source_counts.get(src_key, 0) + 1
            selected.append(b)

        # 4. Partition into Top Items (3 Things to Know) and What Changed
        top_items = selected[:3]
        what_changed = [b for b in selected if b.briefing_type in (BriefingType.UPDATED.value, BriefingType.FOLLOW_UP.value)]

        # 5. Generate Dynamic Intro
        intro = self._generate_personalized_intro(selected, user_topics, daypart)

        return top_items, what_changed, selected, is_caught_up, intro

    def _generate_personalized_intro(
        self,
        selected: List[BriefingCandidate],
        user_topics: List[str],
        daypart: str,
    ) -> str:
        """Generates a concise, contextual introduction string."""
        if not selected:
            return "Here is today's curated briefing based on your reading profile."

        count = len(selected)
        top_candidate_topics = []
        for b in selected[:3]:
            for t in b.candidate.topics:
                if t not in top_candidate_topics:
                    top_candidate_topics.append(t)

        matching = [t for t in top_candidate_topics if any(u.lower() in t.lower() or t.lower() in u.lower() for u in user_topics)]
        other_topics = [t for t in top_candidate_topics if t not in matching]

        if matching and other_topics:
            return f"{matching[0]} leads your {daypart.lower()} updates, alongside important developments in {other_topics[0]}."
        elif matching:
            return f"Here are the top {count} developments in {matching[0]} and your followed topics."
        elif count >= 3:
            return f"Here are the {min(3, count)} biggest developments since your last visit."
        else:
            return f"Here are today's essential updates."
