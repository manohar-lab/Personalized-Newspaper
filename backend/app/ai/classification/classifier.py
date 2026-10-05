"""classifier.py — Phase 7 Topic Classification and Resolution Service.

Maps AI-extracted topics to existing database Topic records, avoids duplicates,
and links topics with confidence scores.
"""
import logging
import re
import uuid
from typing import List, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.classification.schemas import TopicExtractionItem
from app.models.topic import Topic
from app.models.article import article_topics

logger = logging.getLogger(__name__)


def slugify_topic(name: str) -> str:
    """Normalize topic name into a clean URL-friendly slug."""
    text = name.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:100].strip("-")


class TopicClassifier:
    """Manages topic resolution, matching, and database linking with confidence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve_and_link_topics(
        self,
        article_id: uuid.UUID,
        extracted_topics: List[TopicExtractionItem],
        create_missing: bool = True,
    ) -> List[Tuple[Topic, float]]:
        """Match extracted topics to DB topics and link them in article_topics with confidence.
        
        Returns:
            List of (Topic, confidence) tuples
        """
        if not extracted_topics:
            return []

        resolved_links: List[Tuple[Topic, float]] = []

        # Load all existing topics for fast matching
        stmt = select(Topic)
        res = await self.session.execute(stmt)
        existing_topics = list(res.scalars().all())
        slug_to_topic = {t.slug: t for t in existing_topics}
        name_to_topic = {t.name.lower().strip(): t for t in existing_topics}

        # Clear existing topic links for this article before re-linking
        delete_stmt = article_topics.delete().where(article_topics.c.article_id == article_id)
        await self.session.execute(delete_stmt)

        seen_topic_ids = set()

        for item in extracted_topics:
            raw_name = item.name.strip()
            if not raw_name:
                continue

            slug = slugify_topic(raw_name)
            if not slug:
                continue

            target_topic = slug_to_topic.get(slug) or name_to_topic.get(raw_name.lower())

            if not target_topic and create_missing:
                # Create controlled new topic
                target_topic = Topic(
                    id=uuid.uuid4(),
                    name=raw_name.title(),
                    slug=slug,
                    description=f"Topic for {raw_name.title()}",
                )
                self.session.add(target_topic)
                await self.session.flush()
                slug_to_topic[slug] = target_topic
                name_to_topic[raw_name.lower()] = target_topic

            if target_topic and target_topic.id not in seen_topic_ids:
                seen_topic_ids.add(target_topic.id)
                confidence_val = round(float(item.confidence), 4)

                # Insert into article_topics junction table with confidence
                insert_stmt = article_topics.insert().values(
                    article_id=article_id,
                    topic_id=target_topic.id,
                    confidence=confidence_val,
                )
                await self.session.execute(insert_stmt)
                resolved_links.append((target_topic, confidence_val))

        return resolved_links
