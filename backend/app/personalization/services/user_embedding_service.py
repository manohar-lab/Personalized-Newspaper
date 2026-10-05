"""user_embedding_service.py — User Interest Vector Profile Embedding Service.

Builds weighted semantic text representations of user interests and generates/caches
user embeddings for fast, deterministic personalization scoring without runtime AI requests.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.embedder import EmbeddingService
from app.core.config import settings
from app.personalization.models import UserInterestEmbedding

logger = logging.getLogger(__name__)


class UserEmbeddingService:
    """Manages generation, caching, and retrieval of user interest vector embeddings."""

    def __init__(self, session: AsyncSession, embedding_service: Optional[EmbeddingService] = None):
        self.session = session
        self.embedding_service = embedding_service or EmbeddingService()

    @staticmethod
    def build_user_semantic_text(
        positive_interests: Dict[str, float],
        topic_names_map: Optional[Dict[str, str]] = None,
        learned_entities: Optional[Dict[str, float]] = None,
        learned_keywords: Optional[Dict[str, float]] = None,
    ) -> str:
        """Construct structured semantic string from user's positive topic interests, learned entities, and keywords."""
        if not positive_interests and not learned_entities and not learned_keywords:
            return ""

        sections = []

        # 1. Positive & Learned Topics
        if positive_interests:
            topic_parts = []
            sorted_topics = sorted(positive_interests.items(), key=lambda x: x[1], reverse=True)
            for slug, score in sorted_topics:
                display_name = (topic_names_map.get(slug) if topic_names_map else None) or slug.replace("-", " ").title()
                topic_parts.append(f"{display_name} ({score:.2f})")
            sections.append(f"TOPICS: {', '.join(topic_parts)}")

        # 2. Learned Entities
        if learned_entities:
            ent_parts = []
            sorted_ents = sorted(learned_entities.items(), key=lambda x: x[1], reverse=True)
            for name, score in sorted_ents:
                if score >= 0.55:
                    ent_parts.append(f"{name} ({score:.2f})")
            if ent_parts:
                sections.append(f"ENTITIES: {', '.join(ent_parts)}")

        # 3. Learned Keywords
        if learned_keywords:
            kw_parts = []
            sorted_kws = sorted(learned_keywords.items(), key=lambda x: x[1], reverse=True)
            for kw, score in sorted_kws:
                if score >= 0.55:
                    kw_parts.append(f"{kw} ({score:.2f})")
            if kw_parts:
                sections.append(f"KEYWORDS: {', '.join(kw_parts)}")

        return "USER INTEREST PROFILE:\n" + "\n".join(sections)

    async def get_or_create_user_embedding(
        self,
        user_id: uuid.UUID,
        positive_interests: Dict[str, float],
        topic_names_map: Optional[Dict[str, str]] = None,
        learned_entities: Optional[Dict[str, float]] = None,
        learned_keywords: Optional[Dict[str, float]] = None,
        force_refresh: bool = False,
    ) -> Optional[List[float]]:
        """Retrieve cached user embedding or generate and persist a new one."""
        if not positive_interests and not learned_entities and not learned_keywords:
            return None

        embedding_version = settings.ANALYSIS_VERSION

        # 1. Check database cache
        if not force_refresh:
            stmt = select(UserInterestEmbedding).where(
                UserInterestEmbedding.user_id == user_id,
                UserInterestEmbedding.embedding_version == embedding_version,
            )
            result = await self.session.execute(stmt)
            cached = result.scalar_one_or_none()
            if cached and cached.embedding:
                return cached.embedding

        # 2. Generate embedding from weighted profile text
        semantic_text = self.build_user_semantic_text(
            positive_interests=positive_interests,
            topic_names_map=topic_names_map,
            learned_entities=learned_entities,
            learned_keywords=learned_keywords,
        )
        if not semantic_text:
            return None

        try:
            vector = await self.embedding_service.provider.generate_embedding(semantic_text)
            if not vector:
                return None

            # 3. Store / update in database
            stmt = select(UserInterestEmbedding).where(
                UserInterestEmbedding.user_id == user_id,
                UserInterestEmbedding.embedding_version == embedding_version,
            )
            result = await self.session.execute(stmt)
            record = result.scalar_one_or_none()

            now = datetime.now(timezone.utc)
            if record:
                record.embedding = vector
                record.embedding_model = self.embedding_service.provider.model_name
                record.updated_at = now
            else:
                record = UserInterestEmbedding(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    embedding=vector,
                    embedding_model=self.embedding_service.provider.model_name,
                    embedding_version=embedding_version,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(record)

            await self.session.commit()
            return vector

        except Exception as exc:
            logger.error(f"Failed to generate user interest embedding for user {user_id}: {exc}")
            return None

    async def invalidate_user_embedding(self, user_id: uuid.UUID) -> None:
        """Remove cached user embedding after interest changes."""
        stmt = select(UserInterestEmbedding).where(UserInterestEmbedding.user_id == user_id)
        result = await self.session.execute(stmt)
        records = result.scalars().all()
        for r in records:
            await self.session.delete(r)
        await self.session.commit()
