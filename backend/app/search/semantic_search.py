"""semantic_search.py — Phase 11 Vector Semantic Search Engine."""
import logging
import math
import uuid
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.ai.embeddings.embedder import EmbeddingService

logger = logging.getLogger(__name__)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    sim = dot / (norm1 * norm2)
    return float(max(0.0, min(1.0, (sim + 1.0) / 2.0)))  # Normalize [-1, 1] to [0, 1]


class SemanticSearchEngine:
    """
    Reuses existing Article Analysis vector embeddings to score search queries semantically.
    Gracefully falls back to 0.0 if embedding generation is unavailable.
    """

    def __init__(self, session: AsyncSession, embedding_service: Optional[EmbeddingService] = None):
        self.session = session
        self.embedding_service = embedding_service or EmbeddingService()

    async def score_articles_semantically(
        self,
        query: str,
        articles: List[Article],
    ) -> Dict[uuid.UUID, float]:
        """
        Generates query embedding vector and computes cosine similarity against each article's analysis embedding.
        Returns a mapping of {article_id: semantic_score}.
        """
        if not query or not query.strip():
            return {a.id: 0.5 for a in articles}

        query_vector: Optional[List[float]] = None
        try:
            query_vector = await self.embedding_service.provider.generate_embedding(query)
        except Exception as e:
            logger.warning(f"Semantic search embedding generation failed: {e}. Falling back to keyword search.")
            return {a.id: 0.0 for a in articles}

        if not query_vector:
            return {a.id: 0.0 for a in articles}

        scores: Dict[uuid.UUID, float] = {}
        for a in articles:
            art_emb = None
            if hasattr(a, "analysis") and a.analysis:
                art_emb = a.analysis.embedding
            elif hasattr(a, "embedding"):
                art_emb = a.embedding

            if art_emb:
                scores[a.id] = cosine_similarity(query_vector, art_emb)
            else:
                scores[a.id] = 0.0

        return scores
