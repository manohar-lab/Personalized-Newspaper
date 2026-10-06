"""scoring.py — Phase 14 Recommendation Engine Centralized Scoring."""
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import settings
from app.personalization.scoring.semantic_scorer import SemanticScorer
from app.personalization.scoring.topic_scorer import TopicScorer
from app.personalization.scoring.entity_scorer import EntityScorer


class RecommendationScorer:
    """Centralized evaluator for computing comprehensive recommendation scores."""

    def __init__(
        self,
        semantic_weight: float = settings.REC_SEMANTIC_WEIGHT,
        topic_weight: float = settings.REC_TOPIC_WEIGHT,
        entity_weight: float = settings.REC_ENTITY_WEIGHT,
        importance_weight: float = settings.REC_IMPORTANCE_WEIGHT,
        recency_weight: float = settings.REC_RECENCY_WEIGHT,
        novelty_weight: float = settings.REC_NOVELTY_WEIGHT,
        emerging_bonus: float = settings.REC_EMERGING_BONUS,
    ):
        self.semantic_weight = semantic_weight
        self.topic_weight = topic_weight
        self.entity_weight = entity_weight
        self.importance_weight = importance_weight
        self.recency_weight = recency_weight
        self.novelty_weight = novelty_weight
        self.emerging_bonus = emerging_bonus

    @staticmethod
    def _safe_get(obj: Any, attr: str, default=None):
        if isinstance(obj, dict):
            return obj.get(attr, default)
        try:
            return getattr(obj, attr, default)
        except Exception:
            return default

    def compute_recency_score(self, published_at: Optional[datetime], now: Optional[datetime] = None) -> float:
        """Exponential decay based on age in hours relative to RECOMMENDATION_MAX_AGE_HOURS."""
        if not published_at:
            return 0.5
        if now is None:
            now = datetime.now(timezone.utc)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        age_hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
        half_life = float(settings.RECOMMENDATION_MAX_AGE_HOURS)
        decay_lambda = math.log(2) / max(1.0, half_life)
        return round(math.exp(-decay_lambda * age_hours), 4)

    def compute_novelty_score(
        self,
        article: Any,
        recently_read_embeddings: Optional[List[List[float]]] = None,
        top_interest_slug: Optional[str] = None,
    ) -> float:
        """Novelty score is higher when user has not seen similar articles or story introduces new angle."""
        novelty = 1.0

        # Extract article embedding
        analysis = self._safe_get(article, "analysis")
        emb = None
        if analysis:
            emb = self._safe_get(analysis, "embedding")
        elif not isinstance(article, dict) and hasattr(article, "embedding"):
            emb = getattr(article, "embedding")

        # 1. Similarity to recently read articles (if too similar, penalize novelty)
        if emb and recently_read_embeddings:
            max_sim = 0.0
            for r_emb in recently_read_embeddings:
                sim = SemanticScorer.cosine_similarity(emb, r_emb)
                if sim > max_sim:
                    max_sim = sim
            if max_sim > 0.85:
                novelty -= (max_sim - 0.85) * 4.0  # steep drop
            elif max_sim > 0.60:
                novelty -= (max_sim - 0.60) * 1.5

        # 2. Adjacent topic bonus: if article topic is not user's single top dominant topic, novelty gets boost
        topics = self._safe_get(article, "topics", [])
        if top_interest_slug and topics:
            primary_topic_slug = topics[0].slug if hasattr(topics[0], "slug") else str(topics[0])
            if primary_topic_slug != top_interest_slug:
                novelty += 0.15

        return round(max(0.0, min(1.0, novelty)), 4)

    def compute_score(
        self,
        article: Any,
        positive_interests: Dict[str, float],
        negative_interests: Dict[str, float],
        user_embedding: Optional[List[float]] = None,
        learned_entities: Optional[Dict[str, float]] = None,
        recently_read_embeddings: Optional[List[List[float]]] = None,
        recently_recommended_ids: Optional[Set[Any]] = None,
        is_emerging: bool = False,
        now: Optional[datetime] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """Compute consolidated recommendation score normalized between 0.0 and 1.0."""
        # 1. Semantic Similarity
        analysis = self._safe_get(article, "analysis")
        emb = None
        if analysis:
            emb = self._safe_get(analysis, "embedding")
        elif not isinstance(article, dict) and hasattr(article, "embedding"):
            emb = getattr(article, "embedding")

        sem_score = 0.0
        if user_embedding and emb:
            sem_score = max(0.0, SemanticScorer.cosine_similarity(user_embedding, emb))

        # 2. Topic Affinity
        topics = self._safe_get(article, "topics", [])
        topic_slugs = []
        for t in topics:
            if hasattr(t, "slug"):
                topic_slugs.append(t.slug)
            elif isinstance(t, str):
                topic_slugs.append(t)

        top_affinity = 0.0
        if positive_interests and topic_slugs:
            scores = [positive_interests.get(ts, 0.0) for ts in topic_slugs]
            top_affinity = max(scores) if scores else 0.0

        # 3. Entity Affinity
        entities = self._safe_get(article, "entities", [])
        ent_affinity = 0.0
        if learned_entities and entities:
            ent_scores = []
            for e in entities:
                ename = getattr(e, "normalized_name", None) or getattr(e, "name", str(e)).lower().strip()
                if ename in learned_entities:
                    ent_scores.append(learned_entities[ename])
            if ent_scores:
                ent_affinity = min(1.0, sum(ent_scores) / len(ent_scores))

        # 4. Importance
        importance = 0.5
        if analysis:
            importance = getattr(analysis, "importance_score", 0.5)
        elif isinstance(article, dict):
            importance = article.get("importance_score", 0.5)
        importance = max(0.0, min(1.0, float(importance)))

        # 5. Recency
        pub_at = self._safe_get(article, "published_at")
        recency = self.compute_recency_score(pub_at, now=now)

        # 6. Novelty
        top_slug = None
        if positive_interests:
            sorted_pos = sorted(positive_interests.items(), key=lambda x: x[1], reverse=True)
            if sorted_pos:
                top_slug = sorted_pos[0][0]
        novelty = self.compute_novelty_score(
            article,
            recently_read_embeddings=recently_read_embeddings,
            top_interest_slug=top_slug,
        )

        # 7. Emerging Bonus
        em_bonus = self.emerging_bonus if is_emerging else 0.0

        # 8. Negative Penalty
        neg_penalty = 0.0
        if negative_interests and topic_slugs:
            neg_scores = [negative_interests.get(ts, 0.0) for ts in topic_slugs if ts in negative_interests]
            if neg_scores:
                neg_penalty = max(neg_scores) * settings.NEGATIVE_TOPIC_PENALTY

        # 9. Cooldown/Recently Seen Penalty
        recently_seen_pen = 0.0
        art_id = self._safe_get(article, "id")
        if recently_recommended_ids and art_id in recently_recommended_ids:
            recently_seen_pen = 0.35

        # Weighted composite sum
        total_weight = (
            self.semantic_weight
            + self.topic_weight
            + self.entity_weight
            + self.importance_weight
            + self.recency_weight
            + self.novelty_weight
        )
        if total_weight <= 0:
            total_weight = 1.0

        raw_score = (
            self.semantic_weight * sem_score
            + self.topic_weight * top_affinity
            + self.entity_weight * ent_affinity
            + self.importance_weight * importance
            + self.recency_weight * recency
            + self.novelty_weight * novelty
            + em_bonus
            - neg_penalty
            - recently_seen_pen
        )

        final_score = round(max(0.0, min(1.0, raw_score / total_weight if total_weight > 0 else raw_score)), 4)

        breakdown = {
            "semantic_score": round(sem_score, 4),
            "topic_affinity": round(top_affinity, 4),
            "entity_affinity": round(ent_affinity, 4),
            "importance_score": round(importance, 4),
            "recency_score": round(recency, 4),
            "novelty_score": round(novelty, 4),
            "emerging_bonus": round(em_bonus, 4),
            "negative_penalty": round(neg_penalty, 4),
            "recently_seen_penalty": round(recently_seen_pen, 4),
            "final_score": final_score,
        }

        return final_score, breakdown
