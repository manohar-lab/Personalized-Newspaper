"""diversity.py — Multi-source coverage diversity, syndication detection & perspective analysis."""
import re
from typing import Any, Dict, List, Set, Tuple


class CoverageDiversityEngine:
    """Analyzes story clusters to measure source diversity and detect syndicated wire reprints."""

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", (text or "").lower())
        stopwords = {"the", "and", "for", "with", "from", "that", "this", "about", "after", "into", "over"}
        return set(w for w in words if w not in stopwords)

    @classmethod
    def is_syndicated_copy(cls, art_a: Any, art_b: Any) -> bool:
        """
        Determines if art_b is a syndicated duplicate of art_a
        based on near-identical body/description text (> 0.80 Jaccard overlap).
        """
        text_a = getattr(art_a, "content", "") or getattr(art_a, "description", "") or ""
        text_b = getattr(art_b, "content", "") or getattr(art_b, "description", "") or ""

        tokens_a = cls._tokenize(text_a[:1000])
        tokens_b = cls._tokenize(text_b[:1000])

        if not tokens_a or not tokens_b:
            return False

        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        if union == 0:
            return False

        overlap = intersection / union
        return overlap >= 0.80

    @classmethod
    def analyze_cluster_coverage(
        cls,
        articles: List[Any],
    ) -> Tuple[int, int, float, List[Dict[str, Any]]]:
        """
        Analyzes articles in a cluster:
        Returns:
            (total_coverage_count, independent_sources_count, coverage_diversity_score, coverage_items_metadata)
        """
        if not articles:
            return 0, 0, 0.0, []

        total_count = len(articles)
        unique_sources: Set[str] = set()
        syndicated_ids: Set[Any] = set()
        items_meta: List[Dict[str, Any]] = []

        for i, art in enumerate(articles):
            src_name = getattr(art, "source_name", None) or f"Source-{i}"
            unique_sources.add(src_name)

            # Check if syndicated with any previous article in cluster
            is_syndicated = False
            for prev_art in articles[:i]:
                if cls.is_syndicated_copy(prev_art, art):
                    is_syndicated = True
                    syndicated_ids.add(getattr(art, "id", None))
                    break

            items_meta.append({
                "article": art,
                "is_syndicated": is_syndicated,
                "source_name": src_name,
            })

        independent_sources_count = max(1, len(unique_sources) - len(syndicated_ids))
        syndication_ratio = len(syndicated_ids) / float(total_count) if total_count > 0 else 0.0

        # Diversity score scale: 1 independent source = 0.20, 5+ independent = 1.0
        base_diversity = min(1.0, independent_sources_count / 5.0)
        # Apply discount if heavily syndicated
        diversity_score = round(base_diversity * (1.0 - (0.30 * syndication_ratio)), 4)

        return total_count, independent_sources_count, diversity_score, items_meta
