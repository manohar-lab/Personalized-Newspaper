"""extractor.py — Phase 7 Entity Resolution and Storage.

Normalizes extracted named entities, persists distinct entities in the `entities` table,
and establishes links in `article_entities` with confidence scores.
"""
import logging
import re
import uuid
from typing import List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.classification.schemas import EntityExtractionItem, EntityType
from app.models.entity import Entity, article_entities

logger = logging.getLogger(__name__)


def normalize_entity_name(name: str) -> str:
    """Normalize entity name for unique indexing (trimmed, lowercase, collapsed spaces)."""
    cleaned = re.sub(r"\s+", " ", name.strip())
    return cleaned.lower()


class EntityResolver:
    """Resolves and persists entities and links them to articles."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve_and_link_entities(
        self,
        article_id: uuid.UUID,
        extracted_entities: List[EntityExtractionItem],
    ) -> List[Tuple[Entity, float]]:
        """Persist entities and link to article with confidence scores.
        
        Returns:
            List of (Entity, confidence) tuples
        """
        if not extracted_entities:
            return []

        # Clear existing entity links for this article before re-linking
        delete_stmt = article_entities.delete().where(article_entities.c.article_id == article_id)
        await self.session.execute(delete_stmt)

        linked_entities: List[Tuple[Entity, float]] = []
        seen_entity_ids = set()

        for item in extracted_entities:
            raw_name = item.name.strip()
            if not raw_name or len(raw_name) < 2:
                continue

            normalized = normalize_entity_name(raw_name)
            if not normalized:
                continue

            # Look up entity in database
            stmt = select(Entity).where(Entity.normalized_name == normalized)
            res = await self.session.execute(stmt)
            entity = res.scalar_one_or_none()

            etype_str = item.type.value if isinstance(item.type, EntityType) else str(item.type)

            if not entity:
                entity = Entity(
                    id=uuid.uuid4(),
                    name=raw_name,
                    normalized_name=normalized,
                    entity_type=etype_str,
                )
                self.session.add(entity)
                await self.session.flush()

            if entity.id not in seen_entity_ids:
                seen_entity_ids.add(entity.id)
                conf = round(float(item.confidence), 4)

                insert_stmt = article_entities.insert().values(
                    article_id=article_id,
                    entity_id=entity.id,
                    confidence=conf,
                )
                await self.session.execute(insert_stmt)
                linked_entities.append((entity, conf))

        return linked_entities
