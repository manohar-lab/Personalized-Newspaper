"""embedder.py — Phase 7 Semantic Representation and Embedding Service.

Builds structured semantic inputs (TITLE, DESCRIPTION, SUMMARY, TOPICS, KEYWORDS, BODY)
and generates vector embeddings.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.ai.base import EmbeddingProvider
from app.ai.providers.factory import get_embedding_provider

logger = logging.getLogger(__name__)


def build_semantic_text_payload(
    title: str,
    description: Optional[str] = None,
    summary: Optional[str] = None,
    topics: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    body: Optional[str] = None,
    max_body_chars: int = 4000,
) -> str:
    """Construct a clean, structured semantic representation for vector embedding."""
    sections = [f"TITLE: {title.strip()}"]

    if description and description.strip():
        sections.append(f"DESCRIPTION: {description.strip()}")

    if summary and summary.strip():
        sections.append(f"SUMMARY: {summary.strip()}")

    if topics:
        clean_topics = [t.strip() for t in topics if t.strip()]
        if clean_topics:
            sections.append(f"TOPICS: {', '.join(clean_topics)}")

    if keywords:
        clean_keywords = [k.strip() for k in keywords if k.strip()]
        if clean_keywords:
            sections.append(f"KEYWORDS: {', '.join(clean_keywords)}")

    if body and body.strip():
        truncated_body = body.strip()[:max_body_chars]
        sections.append(f"BODY:\n{truncated_body}")

    return "\n\n".join(sections)


class EmbeddingService:
    """Coordinates embedding generation and semantic payload construction."""

    def __init__(self, provider: Optional[EmbeddingProvider] = None):
        self.provider = provider or get_embedding_provider()

    async def generate_article_embedding(
        self,
        title: str,
        description: Optional[str] = None,
        summary: Optional[str] = None,
        topics: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        body: Optional[str] = None,
    ) -> Tuple[Optional[List[float]], Optional[str], Optional[datetime]]:
        """Generate embedding vector for article with metadata.
        
        Returns:
            (embedding_vector, model_name, embedded_at)
        """
        payload = build_semantic_text_payload(
            title=title,
            description=description,
            summary=summary,
            topics=topics,
            keywords=keywords,
            body=body,
        )

        try:
            vector = await self.provider.generate_embedding(payload)
            if vector is not None:
                return vector, self.provider.model_name, datetime.now(timezone.utc)
            return None, None, None
        except Exception as exc:
            logger.error(f"Embedding generation failed: {exc}")
            return None, None, None
