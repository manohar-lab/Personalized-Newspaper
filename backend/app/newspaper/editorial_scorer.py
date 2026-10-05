"""editorial_scorer.py — Multi-Factor Editorial Prioritization & Quality Scorer."""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.personalization.schemas import ScoredArticle
from app.personalization.scoring.recency_scorer import RecencyScorer


@dataclass
class ScoredCandidateStory:
    """Represents a scored article candidate prepared for newspaper edition curation."""
    scored_article: ScoredArticle
    editorial_score: float = 0.5
    quality_score: float = 0.5
    personal_explanation: Optional[str] = None
    cluster_id: Optional[uuid.UUID] = None


class EditorialScorer:
    """Evaluates editorial priority and article publication quality for newspaper layout."""

    def __init__(
        self,
        weight_relevance: float = settings.NEWSPAPER_EDITORIAL_RELEVANCE_WEIGHT,
        weight_importance: float = settings.NEWSPAPER_EDITORIAL_IMPORTANCE_WEIGHT,
        weight_recency: float = settings.NEWSPAPER_EDITORIAL_RECENCY_WEIGHT,
        weight_confidence: float = settings.NEWSPAPER_EDITORIAL_TOPIC_CONF_WEIGHT,
    ):
        self.weight_relevance = weight_relevance
        self.weight_importance = weight_importance
        self.weight_recency = weight_recency
        self.weight_confidence = weight_confidence

    @staticmethod
    def compute_quality_score(article: Any) -> float:
        """Calculate content completeness and publication quality in [0.0, 1.0]."""
        is_full = getattr(article, "is_full_text_available", True)
        if is_full is None:
            is_full = True

        content = getattr(article, "content", "") or ""
        length_ratio = min(1.0, len(content.strip()) / 1500.0) if content else 0.3

        has_image = bool(getattr(article, "image_url", None) or getattr(article, "top_image_url", None))
        has_author = bool(getattr(article, "author", None))

        quality = (
            (1.0 if is_full else 0.4) * 0.40
            + length_ratio * 0.30
            + (1.0 if has_image else 0.0) * 0.15
            + (1.0 if has_author else 0.0) * 0.15
        )
        return round(max(0.0, min(1.0, quality)), 4)

    def compute_editorial_score(
        self,
        article: Any,
        personal_relevance: float,
        recency_score: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> float:
        """Calculate final editorial placement score combining relevance, global importance, recency, and topic confidence."""
        # 1. Global Importance
        importance = getattr(article, "importance_score", None)
        if importance is None and hasattr(article, "analysis") and article.analysis:
            importance = getattr(article.analysis, "importance_score", 0.5)
        elif isinstance(article, dict):
            importance = article.get("importance_score", 0.5)
        if importance is None:
            importance = 0.5
        importance = max(0.0, min(1.0, float(importance)))

        # 2. Recency
        if recency_score is None:
            pub_at = getattr(article, "published_at", None)
            created_at = getattr(article, "created_at", None)
            recency = RecencyScorer.score_recency(pub_at, created_at, now=now)
        else:
            recency = recency_score

        # 3. Topic Confidence
        topic_conf = 1.0
        topics = getattr(article, "topics", [])
        if topics:
            first_top = topics[0]
            conf = getattr(first_top, "confidence", 1.0)
            try:
                topic_conf = float(conf)
            except (TypeError, ValueError):
                topic_conf = 1.0
        topic_conf = max(0.0, min(1.0, topic_conf))

        # 4. Weighted combination (Personal relevance is dominant)
        score = (
            personal_relevance * self.weight_relevance
            + importance * self.weight_importance
            + recency * self.weight_recency
            + topic_conf * self.weight_confidence
        )
        return round(max(0.0, min(1.0, score)), 4)

    def score_candidates(
        self,
        candidates: List[ScoredArticle],
        cluster_map: Optional[Dict[uuid.UUID, uuid.UUID]] = None,
        now: Optional[datetime] = None,
    ) -> List[ScoredCandidateStory]:
        """Scores a list of candidate articles and wraps them as ScoredCandidateStory."""
        results: List[ScoredCandidateStory] = []
        c_map = cluster_map or {}

        for cand in candidates:
            art = cand.article
            ed_score = self.compute_editorial_score(
                article=art,
                personal_relevance=cand.relevance_score,
                recency_score=cand.breakdown.recency_score if cand.breakdown else None,
                now=now,
            )
            q_score = self.compute_quality_score(art)
            cluster_id = c_map.get(art.id)

            results.append(
                ScoredCandidateStory(
                    scored_article=cand,
                    editorial_score=ed_score,
                    quality_score=q_score,
                    cluster_id=cluster_id,
                )
            )

        # Sort descending by editorial score
        results.sort(key=lambda s: s.editorial_score, reverse=True)
        return results
