"""topic_scorer.py — Multi-factor Topic Relevance and Penalty Scorer.

Calculates positive topic alignment:
    article_topic_score = topic_confidence × user_interest_score
and negative penalties:
    negative_penalty = topic_confidence × user_negative_interest × penalty_multiplier
"""
from typing import Any, Dict, List, Optional, Tuple, Union
from app.core.config import settings


class TopicScorer:
    """Evaluates article topics against user's positive interests and negative preferences."""

    @staticmethod
    def _extract_topics_with_confidence(article_topics: Any) -> List[Tuple[str, float]]:
        """Normalize various topic input formats to list of (slug, confidence)."""
        result = []
        if not article_topics:
            return result

        for t in article_topics:
            if isinstance(t, tuple) or isinstance(t, list):
                slug = str(t[0]).lower().strip()
                conf = float(t[1]) if len(t) > 1 else 1.0
                result.append((slug, conf))
            elif hasattr(t, "slug"):
                slug = str(t.slug).lower().strip()
                # Check for junction confidence if available or default to 1.0
                conf = getattr(t, "confidence", 1.0)
                try:
                    conf = float(conf)
                except (TypeError, ValueError):
                    conf = 1.0
                result.append((slug, conf))
            elif isinstance(t, dict):
                slug = str(t.get("slug") or t.get("name") or "").lower().strip()
                conf = float(t.get("confidence", 1.0))
                result.append((slug, conf))
            elif isinstance(t, str):
                result.append((t.lower().strip(), 1.0))
        return result

    @classmethod
    def score_topics(
        cls,
        article_topics: Any,
        positive_interests: Dict[str, float],
        negative_interests: Dict[str, float],
        negative_penalty_weight: Optional[float] = None,
    ) -> Tuple[float, float]:
        """Compute (positive_topic_score, negative_penalty).
        
        Returns:
            topic_score: float in [0.0, 1.0]
            negative_penalty: float >= 0.0
        """
        penalty_multiplier = (
            negative_penalty_weight
            if negative_penalty_weight is not None
            else settings.NEGATIVE_TOPIC_PENALTY
        )

        extracted = cls._extract_topics_with_confidence(article_topics)
        if not extracted:
            return 0.0, 0.0

        # 1. Calculate positive contributions
        pos_contributions: List[float] = []
        for slug, conf in extracted:
            # Match by slug or normalized name
            user_score = positive_interests.get(slug)
            if user_score is not None and user_score > 0:
                pos_contributions.append(conf * user_score)

        # 2. Calculate negative penalties
        neg_penalties: List[float] = []
        for slug, conf in extracted:
            neg_score = negative_interests.get(slug)
            if neg_score is not None and neg_score > 0:
                neg_penalties.append(conf * neg_score * penalty_multiplier)

        # Topic score normalization:
        # If single topic matched, e.g. conf 0.8 * score 0.9 = 0.72
        # If multiple topics matched, combine them gracefully clamped to 1.0
        if pos_contributions:
            # We can use max or sum-normalized:
            # max(pos_contributions) + small residual bonus for multiple matching topics
            base_score = max(pos_contributions)
            residual = sum(pos_contributions) - base_score
            topic_score = min(1.0, base_score + 0.15 * residual)
            topic_score = max(0.0, min(1.0, topic_score))
        else:
            topic_score = 0.0

        total_penalty = sum(neg_penalties)
        if total_penalty < 0.0:
            total_penalty = 0.0

        return round(topic_score, 4), round(total_penalty, 4)
