"""semantic_scorer.py — Vector Embedding Cosine Similarity Scorer.

Computes cosine similarity between user interest profile vector and article embedding vector.
"""
import math
from typing import List, Optional


class SemanticScorer:
    """Evaluates semantic similarity between user interest embedding and article embedding."""

    @staticmethod
    def cosine_similarity(
        vector_a: Optional[List[float]],
        vector_b: Optional[List[float]],
    ) -> float:
        """Calculate cosine similarity between two vectors.
        
        Returns:
            Cosine similarity in [-1.0, 1.0], or 0.0 if vectors are invalid/zero-norm.
        """
        if not vector_a or not vector_b:
            return 0.0

        if len(vector_a) != len(vector_b):
            # If lengths mismatch, truncate to common dimension
            min_len = min(len(vector_a), len(vector_b))
            if min_len == 0:
                return 0.0
            vector_a = vector_a[:min_len]
            vector_b = vector_b[:min_len]

        dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
        norm_a = math.sqrt(sum(a * a for a in vector_a))
        norm_b = math.sqrt(sum(b * b for b in vector_b))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        similarity = dot_product / (norm_a * norm_b)
        if math.isnan(similarity) or math.isinf(similarity):
            return 0.0

        return max(-1.0, min(1.0, similarity))

    @classmethod
    def score_semantic(
        cls,
        user_embedding: Optional[List[float]],
        article_embedding: Optional[List[float]],
        default_neutral_score: float = 0.5,
    ) -> float:
        """Compute normalized semantic relevance score in [0.0, 1.0].
        
        If user or article embedding is missing, returns neutral fallback.
        """
        if not user_embedding or not article_embedding:
            return default_neutral_score

        cos_sim = cls.cosine_similarity(user_embedding, article_embedding)
        # Rescale [-1.0, 1.0] -> [0.0, 1.0]
        # (sim + 1) / 2
        normalized = (cos_sim + 1.0) / 2.0
        normalized = max(0.0, min(1.0, normalized))
        return round(normalized, 4)
