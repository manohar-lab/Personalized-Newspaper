"""diversity.py — Phase 17 Editorial Multi-Dimensional Diversity & Anti-Monopoly Filter."""
from typing import Any, Dict, List, Set, Tuple
from app.editorial.schemas import EditorialCandidate, EditorialWeights


class EditorialDiversityFilter:
    """Applies multi-dimensional diversity across topics, entities, sources, and sections."""

    def __init__(
        self,
        weights: EditorialWeights = None,
        max_consecutive_same_topic: int = 2,
        max_same_topic_count: int = 5,
        entity_repeat_penalty: float = 0.15,
        source_monopoly_penalty: float = 0.10,
    ):
        self.weights = weights or EditorialWeights()
        self.max_consecutive_same_topic = max_consecutive_same_topic
        self.max_same_topic_count = max_same_topic_count
        self.entity_repeat_penalty = entity_repeat_penalty
        self.source_monopoly_penalty = source_monopoly_penalty

    def apply_diversity(
        self,
        ranked_candidates: List[EditorialCandidate],
        target_count: int = 25,
    ) -> Tuple[List[EditorialCandidate], Dict[str, Any]]:
        """
        Iteratively selects candidates while applying real-time penalties for topic, entity,
        and source clustering to ensure broad, balanced, non-monopolized editorial coverage.
        
        Returns:
            (selected_candidates, diversity_audit_metadata)
        """
        if not ranked_candidates:
            return [], {"topic_distribution": {}, "entity_distribution": {}, "source_distribution": {}}

        selected: List[EditorialCandidate] = []
        remaining = list(ranked_candidates)

        topic_counts: Dict[str, int] = {}
        entity_counts: Dict[str, int] = {}
        source_counts: Dict[str, int] = {}
        consecutive_topic = ""
        consecutive_count = 0

        while remaining and len(selected) < target_count:
            # Dynamically recalculate candidate desirability based on current selection state
            best_idx = 0
            best_adjusted_score = -999.0

            for idx, cand in enumerate(remaining):
                primary_cat = (cand.primary_category or "GENERAL").upper()
                curr_topic_count = topic_counts.get(primary_cat, 0)
                
                # Base score
                adjusted_score = cand.editorial_score

                # 1. Topic saturation penalty
                if curr_topic_count >= self.max_same_topic_count:
                    # Heavy penalty for going over max topic budget
                    adjusted_score -= 0.35 * (curr_topic_count - self.max_same_topic_count + 1)
                elif curr_topic_count > 2:
                    adjusted_score -= 0.08 * (curr_topic_count - 2)

                # 2. Consecutive topic penalty
                if primary_cat == consecutive_topic and consecutive_count >= self.max_consecutive_same_topic:
                    adjusted_score -= 0.25

                # 3. Entity repeat penalty
                for ent in cand.entities:
                    ent_cnt = entity_counts.get(ent.lower(), 0)
                    if ent_cnt > 0:
                        adjusted_score -= self.entity_repeat_penalty * ent_cnt

                # 4. Source monopoly penalty
                if cand.source_name:
                    src_cnt = source_counts.get(cand.source_name, 0)
                    if src_cnt >= 3:
                        adjusted_score -= self.source_monopoly_penalty * (src_cnt - 2)

                # 5. Public Importance preservation: high importance items resist excessive diversity penalty
                if cand.importance_score >= 0.85:
                    adjusted_score += 0.10

                if adjusted_score > best_adjusted_score:
                    best_adjusted_score = adjusted_score
                    best_idx = idx

            chosen = remaining.pop(best_idx)
            selected.append(chosen)

            # Update selection distribution trackers
            chosen_cat = (chosen.primary_category or "GENERAL").upper()
            topic_counts[chosen_cat] = topic_counts.get(chosen_cat, 0) + 1

            if chosen_cat == consecutive_topic:
                consecutive_count += 1
            else:
                consecutive_topic = chosen_cat
                consecutive_count = 1

            for ent in chosen.entities:
                key = ent.lower()
                entity_counts[key] = entity_counts.get(key, 0) + 1

            if chosen.source_name:
                source_counts[chosen.source_name] = source_counts.get(chosen.source_name, 0) + 1

        diversity_audit = {
            "topic_distribution": topic_counts,
            "entity_distribution": entity_counts,
            "source_distribution": source_counts,
            "total_evaluated": len(ranked_candidates),
            "total_selected": len(selected),
        }

        return selected, diversity_audit
