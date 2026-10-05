"""relevance_scorer.py — Multi-Factor Personal Relevance Master Scorer.

Combines topic, semantic, entity, keyword, importance, and recency scores
with configurable weights and negative topic penalties.
"""
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.personalization.schemas import RelevanceScoreBreakdown
from app.personalization.scoring.topic_scorer import TopicScorer
from app.personalization.scoring.semantic_scorer import SemanticScorer
from app.personalization.scoring.entity_scorer import EntityScorer
from app.personalization.scoring.keyword_scorer import KeywordScorer
from app.personalization.scoring.recency_scorer import RecencyScorer


class RelevanceScorer:
    """Master evaluator computing deterministic personal relevance for (user, article)."""

    def __init__(
        self,
        topic_weight: Optional[float] = None,
        semantic_weight: Optional[float] = None,
        entity_weight: Optional[float] = None,
        keyword_weight: Optional[float] = None,
        importance_weight: Optional[float] = None,
        recency_weight: Optional[float] = None,
        negative_penalty_weight: Optional[float] = None,
    ):
        self.topic_weight = topic_weight if topic_weight is not None else settings.PERSONALIZATION_TOPIC_WEIGHT
        self.semantic_weight = semantic_weight if semantic_weight is not None else settings.PERSONALIZATION_SEMANTIC_WEIGHT
        self.entity_weight = entity_weight if entity_weight is not None else settings.PERSONALIZATION_ENTITY_WEIGHT
        self.keyword_weight = keyword_weight if keyword_weight is not None else settings.PERSONALIZATION_KEYWORD_WEIGHT
        self.importance_weight = importance_weight if importance_weight is not None else settings.PERSONALIZATION_IMPORTANCE_WEIGHT
        self.recency_weight = recency_weight if recency_weight is not None else settings.PERSONALIZATION_RECENCY_WEIGHT
        self.negative_penalty_weight = (
            negative_penalty_weight
            if negative_penalty_weight is not None
            else settings.NEGATIVE_TOPIC_PENALTY
        )

    def compute_relevance(
        self,
        article: Any,
        positive_interests: Dict[str, float],
        negative_interests: Dict[str, float],
        user_embedding: Optional[List[float]] = None,
        positive_topic_names: Optional[List[str]] = None,
        now: Optional[datetime] = None,
    ) -> Tuple[float, RelevanceScoreBreakdown]:
        """Compute multi-factor personal relevance score and detailed breakdown.
        
        Handles both ORM Article instances and plain test dicts/objects.
        """
        has_user_interests = bool(positive_interests or negative_interests)

        # 1. Extract Article fields
        topics = getattr(article, "topics", [])
        if isinstance(article, dict):
            topics = article.get("topics", [])

        entities = getattr(article, "entities", [])
        if isinstance(article, dict):
            entities = article.get("entities", [])

        keywords = getattr(article, "keywords", [])
        if isinstance(article, dict):
            keywords = article.get("keywords", [])

        # Importance score
        importance = getattr(article, "importance_score", None)
        if importance is None and hasattr(article, "analysis") and article.analysis:
            importance = getattr(article.analysis, "importance_score", 0.5)
        elif isinstance(article, dict):
            importance = article.get("importance_score", 0.5)
        if importance is None:
            importance = 0.5
        importance = max(0.0, min(1.0, float(importance)))

        # Article Embedding
        article_embedding = None
        if hasattr(article, "analysis") and article.analysis:
            article_embedding = getattr(article.analysis, "embedding", None)
        elif hasattr(article, "embedding"):
            article_embedding = getattr(article, "embedding")
        elif isinstance(article, dict):
            article_embedding = article.get("embedding")

        # Publication & Creation dates
        published_at = getattr(article, "published_at", None)
        created_at = getattr(article, "created_at", None)
        if isinstance(article, dict):
            published_at = article.get("published_at")
            created_at = article.get("created_at")

        # 2. Topic Scoring & Negative Penalty
        topic_score, negative_penalty = TopicScorer.score_topics(
            article_topics=topics,
            positive_interests=positive_interests,
            negative_interests=negative_interests,
            negative_penalty_weight=self.negative_penalty_weight,
        )

        # 3. Semantic Embedding Similarity
        # If user has no interests, default neutral 0.5
        semantic_score = SemanticScorer.score_semantic(
            user_embedding=user_embedding,
            article_embedding=article_embedding,
            default_neutral_score=0.5 if has_user_interests else 0.5,
        )

        # 4. Entity Relevance
        entity_score = EntityScorer.score_entities(
            article_entities=entities,
            positive_interests=positive_interests,
            positive_topic_names=positive_topic_names,
            default_neutral_score=0.5,
        )

        # 5. Keyword Relevance
        keyword_score = KeywordScorer.score_keywords(
            article_keywords=keywords,
            positive_interests=positive_interests,
            positive_topic_names=positive_topic_names,
            default_neutral_score=0.5,
        )

        # 6. Recency Decay
        recency_score = RecencyScorer.score_recency(
            published_at=published_at,
            created_at=created_at,
            now=now,
        )

        # 7. Weighted combination
        if not has_user_interests:
            # Cold-start / No interests profile:
            # Balance importance, recency, and neutral semantic baseline
            raw_score = (
                importance * (self.importance_weight + self.topic_weight * 0.5)
                + recency_score * (self.recency_weight + self.semantic_weight * 0.5)
                + 0.5 * (self.entity_weight + self.keyword_weight)
            )
        else:
            raw_score = (
                topic_score * self.topic_weight
                + semantic_score * self.semantic_weight
                + entity_score * self.entity_weight
                + keyword_score * self.keyword_weight
                + importance * self.importance_weight
                + recency_score * self.recency_weight
            )

        # 8. Apply negative penalty
        net_score = raw_score - negative_penalty

        # Clamp and sanitize
        if math.isnan(net_score) or math.isinf(net_score):
            final_score = 0.0
        else:
            final_score = max(0.0, min(1.0, net_score))

        final_score = round(final_score, 4)

        breakdown = RelevanceScoreBreakdown(
            final_score=final_score,
            topic_score=round(topic_score, 4),
            semantic_score=round(semantic_score, 4),
            entity_score=round(entity_score, 4),
            keyword_score=round(keyword_score, 4),
            importance_score=round(importance, 4),
            recency_score=round(recency_score, 4),
            negative_penalty=round(negative_penalty, 4),
            source_score=0.0,
        )

        return final_score, breakdown
