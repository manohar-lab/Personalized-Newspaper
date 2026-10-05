from typing import List, Dict, Set, Optional, Tuple
from app.core.config import settings
from app.personalization.schemas import ScoredArticle
from app.newspaper.editorial_scorer import ScoredCandidateStory


class DiversityFilter:
    """
    Applies topic and entity diversity rules to a ranked candidate list.
    Prevents topic monopoly, enforces soft topic caps, applies entity repetition penalties,
    and generates clear, non-invasive personalization explanations.
    """

    def __init__(
        self,
        max_consecutive_same_topic: int = settings.NEWSPAPER_MAX_CONSECUTIVE_SAME_TOPIC,
        entity_repeat_penalty: float = settings.NEWSPAPER_ENTITY_REPEAT_PENALTY,
    ):
        self.max_consecutive_same_topic = max_consecutive_same_topic
        self.entity_repeat_penalty = entity_repeat_penalty

    def apply_diversity(
        self,
        candidates: List[ScoredCandidateStory],
        user_top_interests: Optional[List[str]] = None,
    ) -> List[ScoredCandidateStory]:
        """
        Reorders candidates to prevent consecutive topic clustering and penalize entity overuse,
        while attaching user-friendly personalization explanation tags.
        """
        if not candidates:
            return []

        user_top_interests_lower = (
            [t.lower() for t in user_top_interests] if user_top_interests else []
        )

        # 1. Calculate adjusted scores considering entity frequency
        entity_counts: Dict[str, int] = {}
        adjusted_candidates: List[ScoredCandidateStory] = []

        for candidate in candidates:
            article = candidate.scored_article.article
            entities = article.entities or []
            
            # Count how many times entities in this article have already appeared
            max_entity_repeat = 0
            for ent in entities:
                ent_name = ent.get("name", "").strip().lower() if isinstance(ent, dict) else str(ent).strip().lower()
                if ent_name:
                    max_entity_repeat = max(max_entity_repeat, entity_counts.get(ent_name, 0))

            # Apply penalty
            penalty = max_entity_repeat * self.entity_repeat_penalty
            adjusted_score = max(0.0, candidate.editorial_score - penalty)

            # Generate personalization explanation
            explanation = self._generate_explanation(candidate, user_top_interests_lower)

            adjusted_candidate = ScoredCandidateStory(
                scored_article=candidate.scored_article,
                editorial_score=adjusted_score,
                quality_score=candidate.quality_score,
                personal_explanation=explanation,
                cluster_id=candidate.cluster_id,
            )
            adjusted_candidates.append(adjusted_candidate)

            # Update entity counts for subsequent stories
            for ent in entities:
                ent_name = ent.get("name", "").strip().lower() if isinstance(ent, dict) else str(ent).strip().lower()
                if ent_name:
                    entity_counts[ent_name] = entity_counts.get(ent_name, 0) + 1

        # Sort by adjusted editorial score
        sorted_candidates = sorted(
            adjusted_candidates, key=lambda c: c.editorial_score, reverse=True
        )

        # 2. Interleave to prevent consecutive topic monopoly (e.g. max 2 consecutive of same category/topic)
        diversified: List[ScoredCandidateStory] = []
        deferred: List[ScoredCandidateStory] = []
        current_topic = None
        consecutive_topic_count = 0

        for candidate in sorted_candidates:
            art = candidate.scored_article.article
            first_topic = "OTHER"
            if art.topics:
                t0 = art.topics[0]
                first_topic = t0.name if hasattr(t0, "name") else str(t0)

            topic = (
                art.primary_category
                or first_topic
            ).upper()

            if topic == current_topic:
                if consecutive_topic_count >= self.max_consecutive_same_topic:
                    # Defer this candidate to later
                    deferred.append(candidate)
                    continue
                else:
                    consecutive_topic_count += 1
            else:
                current_topic = topic
                consecutive_topic_count = 1

            diversified.append(candidate)

            # Try to drain deferred items if topic changed
            if deferred:
                remaining_deferred = []
                for def_cand in deferred:
                    d_art = def_cand.scored_article.article
                    d_first_topic = "OTHER"
                    if d_art.topics:
                        dt0 = d_art.topics[0]
                        d_first_topic = dt0.name if hasattr(dt0, "name") else str(dt0)

                    def_topic = (
                        d_art.primary_category
                        or d_first_topic
                    ).upper()
                    if def_topic != current_topic:
                        diversified.append(def_cand)
                        current_topic = def_topic
                        consecutive_topic_count = 1
                    else:
                        remaining_deferred.append(def_cand)
                deferred = remaining_deferred

        # Append any remaining deferred at the end
        diversified.extend(deferred)
        return diversified

    def _generate_explanation(
        self, candidate: ScoredCandidateStory, user_interests_lower: List[str]
    ) -> str:
        """
        Generates a subtle, user-facing reason:
        e.g., 'Because you follow Artificial Intelligence' or 'Top story in Technology'.
        """
        article = candidate.scored_article.article
        topics = [
            (t.name.lower() if hasattr(t, "name") else str(t).lower())
            for t in (getattr(article, "topics", []) or [])
        ]
        category = (article.primary_category or "").lower()

        # Check for intersection with user explicit/learned interests
        matching_topics = [t for t in topics if t in user_interests_lower]
        if matching_topics:
            return f"Matches your interest in {matching_topics[0].title()}"
        
        if category in user_interests_lower:
            return f"Because you follow {category.title()}"

        if topics:
            return f"Trending in {topics[0].title()}"
        if category:
            return f"Top story in {category.title()}"
        return "Recommended for you today"
