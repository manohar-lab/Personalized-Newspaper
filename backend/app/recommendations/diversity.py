"""diversity.py — Multi-Level Recommendation Diversity & Exploration Engine."""
import random
from typing import Any, Dict, List, Optional, Set, Tuple
from app.core.config import settings


class RecommendationDiversityEngine:
    """Applies exploitation vs exploration balance, topic limits, entity repetition penalties, and source diversification."""

    def __init__(
        self,
        exploitation_ratio: float = settings.RECOMMENDATION_EXPLOITATION_RATIO,
        exploration_ratio: float = settings.RECOMMENDATION_EXPLORATION_RATIO,
        max_per_topic: int = settings.RECOMMENDATION_MAX_PER_TOPIC,
    ):
        self.exploitation_ratio = exploitation_ratio
        self.exploration_ratio = exploration_ratio
        self.max_per_topic = max_per_topic

    @staticmethod
    def _safe_get(obj: Any, attr: str, default=None):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        try:
            return getattr(obj, attr, default)
        except Exception:
            return default

    def _get_primary_topic(self, article: Any) -> Optional[str]:
        topics = self._safe_get(article, "topics", [])
        if topics:
            first = topics[0]
            if hasattr(first, "slug"):
                return first.slug
            if isinstance(first, str):
                return first
        analysis = self._safe_get(article, "analysis")
        if analysis:
            cat = getattr(analysis, "primary_category", None)
            if cat:
                return cat.lower().strip()
        return None

    def _get_dominant_entities(self, article: Any) -> Set[str]:
        entities = self._safe_get(article, "entities", [])
        res = set()
        for e in entities:
            name = getattr(e, "normalized_name", None) or getattr(e, "name", str(e)).lower().strip()
            if name:
                res.add(name)
        return res

    def _get_source_name(self, article: Any) -> Optional[str]:
        sname = self._safe_get(article, "source_name")
        if not sname:
            source = self._safe_get(article, "source")
            if source:
                sname = getattr(source, "name", None)
        return (sname or "").lower().strip() or None

    def apply_diversity_and_exploration(
        self,
        scored_candidates: List[Tuple[Any, float, Dict[str, Any]]],
        limit: int = 20,
        top_dominant_topic: Optional[str] = None,
    ) -> List[Tuple[Any, float, Dict[str, Any]]]:
        """Apply topic capping, entity anti-repetition, source mixing, and exploration ratio."""
        if not scored_candidates:
            return []

        # Sort candidates descending by score
        sorted_candidates = sorted(scored_candidates, key=lambda x: x[1], reverse=True)

        n_exploit = max(1, int(limit * self.exploitation_ratio))
        n_explore = limit - n_exploit

        exploit_selected: List[Tuple[Any, float, Dict[str, Any]]] = []
        explore_selected: List[Tuple[Any, float, Dict[str, Any]]] = []

        topic_counts: Dict[str, int] = {}
        entity_counts: Dict[str, int] = {}
        selected_ids: Set[Any] = set()

        # Phase 1: Exploitation Selection (Top strongly relevant articles)
        for cand in sorted_candidates:
            if len(exploit_selected) >= n_exploit:
                break
            art, score, breakdown = cand
            art_id = self._safe_get(art, "id")
            if art_id in selected_ids:
                continue

            topic = self._get_primary_topic(art)
            if topic and topic_counts.get(topic, 0) >= self.max_per_topic:
                continue  # Topic limit reached for exploitation

            # Check entity caps (max 2 articles per entity)
            ents = self._get_dominant_entities(art)
            if any(entity_counts.get(e, 0) >= 2 for e in ents):
                continue

            exploit_selected.append(cand)
            selected_ids.add(art_id)
            if topic:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
            for e in ents:
                entity_counts[e] = entity_counts.get(e, 0) + 1

        # Phase 2: Exploration Selection (Adjacent discovery topics/entities outside top dominant topic)
        for cand in sorted_candidates:
            if len(explore_selected) >= n_explore:
                break
            art, score, breakdown = cand
            art_id = self._safe_get(art, "id")
            if art_id in selected_ids:
                continue

            topic = self._get_primary_topic(art)

            # Exploration favors articles from adjacent topics (not the #1 dominant topic)
            if top_dominant_topic and topic == top_dominant_topic and len(sorted_candidates) > len(selected_ids) + 5:
                continue

            if topic and topic_counts.get(topic, 0) >= self.max_per_topic + 1:
                continue

            # Mark breakdown reason as DISCOVERY if it's an exploration pick
            breakdown_copy = dict(breakdown)
            breakdown_copy["is_exploration"] = True

            explore_selected.append((art, score, breakdown_copy))
            selected_ids.add(art_id)
            if topic:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # Combine exploit + explore
        combined = exploit_selected + explore_selected

        # If combined is less than limit, backfill remaining candidates
        if len(combined) < limit:
            for cand in sorted_candidates:
                if len(combined) >= limit:
                    break
                art_id = self._safe_get(cand[0], "id")
                if art_id not in selected_ids:
                    combined.append(cand)
                    selected_ids.add(art_id)

        # Phase 3: Source Diversity Re-ordering (Avoid 3 consecutive same publishers)
        final_list: List[Tuple[Any, float, Dict[str, Any]]] = []
        remaining = list(combined)

        while remaining:
            if not final_list:
                final_list.append(remaining.pop(0))
                continue

            last_source = self._get_source_name(final_list[-1][0])
            next_idx = 0

            # If last article had a source, look for next candidate with different source
            if last_source:
                found_different = False
                for i, c in enumerate(remaining):
                    c_source = self._get_source_name(c[0])
                    if c_source != last_source:
                        next_idx = i
                        found_different = True
                        break
                if not found_different:
                    next_idx = 0

            final_list.append(remaining.pop(next_idx))

        return final_list[:limit]
