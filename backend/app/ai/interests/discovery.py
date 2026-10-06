"""discovery.py — Hierarchical Topic Propagation and Related Topic Discovery Engine.

Handles propagation of interest up topic taxonomy (parent, grandparent) and dynamic
discovery of related topics based on repeated interaction evidence thresholds.
"""
import logging
import uuid
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.topic import Topic

logger = logging.getLogger(__name__)


class TopicPropagationEngine:
    """Manages hierarchical topic propagation and related topic discovery."""

    @staticmethod
    async def get_ancestor_topics(
        session: AsyncSession,
        topic_id: uuid.UUID,
    ) -> List[Tuple[Topic, float]]:
        """Find parent and grandparent topics with decay propagation weights.
        
        Returns:
            List of (Topic, weight) where parent = 0.50, grandparent = 0.25
        """
        ancestors: List[Tuple[Topic, float]] = []

        stmt = (
            select(Topic)
            .where(Topic.id == topic_id)
            .options(
                selectinload(Topic.parent_topic).selectinload(Topic.parent_topic)
            )
        )
        res = await session.execute(stmt)
        topic = res.scalar_one_or_none()
        if not topic:
            return ancestors

        parent = topic.parent_topic
        if parent:
            ancestors.append((parent, settings.PROPAGATION_PARENT_WEIGHT))
            grandparent = parent.parent_topic
            if grandparent:
                ancestors.append((grandparent, settings.PROPAGATION_GRANDPARENT_WEIGHT))

        return ancestors

    @staticmethod
    def should_promote_inferred_topic(evidence_count: int, positive_count: int) -> bool:
        """Determines if candidate inferred topic has crossed discovery evidence threshold."""
        return (
            evidence_count >= settings.MIN_DISCOVERY_EVIDENCE
            and positive_count >= (evidence_count * 0.6)
        )
