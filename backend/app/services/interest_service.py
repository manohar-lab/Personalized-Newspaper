import uuid
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.models.topic import Topic
from app.models.interest import UserInterest
from app.personalization.models import UserInterestEmbedding

class InterestService:
    @staticmethod
    async def get_user_interests(
        session: AsyncSession, user_id: uuid.UUID
    ) -> List[UserInterest]:
        """Fetch all interest preferences for a given user."""
        stmt = (
            select(UserInterest)
            .options(selectinload(UserInterest.topic))
            .where(UserInterest.user_id == user_id)
            .order_by(UserInterest.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def set_user_interest(
        session: AsyncSession,
        user_id: uuid.UUID,
        topic_slug: str,
        interest_score: float,
        preference_type: str,
        source: str = "USER_ACTION",
    ) -> UserInterest:
        """Create or update a user's interest preference for a topic."""
        # 1. Validate score range
        if not (0.0 <= interest_score <= 1.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="interest_score must be between 0.0 and 1.0",
            )

        preference_type = preference_type.upper()
        if preference_type not in ("POSITIVE", "NEGATIVE"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="preference_type must be POSITIVE or NEGATIVE",
            )

        # 2. Lookup topic by slug
        stmt_topic = select(Topic).where(Topic.slug == topic_slug)
        result_topic = await session.execute(stmt_topic)
        topic = result_topic.scalar_one_or_none()
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic with slug '{topic_slug}' not found",
            )

        # 3. Check for existing interest record
        stmt_interest = select(UserInterest).where(
            UserInterest.user_id == user_id,
            UserInterest.topic_id == topic.id,
        )
        result_interest = await session.execute(stmt_interest)
        interest = result_interest.scalar_one_or_none()

        if interest:
            interest.interest_score = interest_score
            interest.preference_type = preference_type
            interest.source = source
        else:
            interest = UserInterest(
                user_id=user_id,
                topic_id=topic.id,
                interest_score=interest_score,
                preference_type=preference_type,
                source=source,
            )
            session.add(interest)

        # Invalidate cached user interest embedding
        await session.execute(
            delete(UserInterestEmbedding).where(UserInterestEmbedding.user_id == user_id)
        )
        await session.commit()
        await session.refresh(interest, attribute_names=["topic"])
        return interest

    @staticmethod
    async def remove_user_interest(
        session: AsyncSession, user_id: uuid.UUID, topic_slug: str
    ) -> bool:
        """Remove a user's interest preference for a topic."""
        # Lookup topic
        stmt_topic = select(Topic).where(Topic.slug == topic_slug)
        result_topic = await session.execute(stmt_topic)
        topic = result_topic.scalar_one_or_none()
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic with slug '{topic_slug}' not found",
            )

        stmt_delete = delete(UserInterest).where(
            UserInterest.user_id == user_id,
            UserInterest.topic_id == topic.id,
        )
        result = await session.execute(stmt_delete)
        # Invalidate cached user interest embedding
        await session.execute(
            delete(UserInterestEmbedding).where(UserInterestEmbedding.user_id == user_id)
        )
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def initialize_onboarding_interests(
        session: AsyncSession,
        user_id: uuid.UUID,
        positive_topics: List[str],
        negative_topics: List[str],
    ) -> List[UserInterest]:
        """
        Process initial onboarding selections.
        Assigns default initial score of 0.80 for positive and 0.80 for negative.
        Validates all topics before persisting.
        """
        DEFAULT_SCORE = 0.80
        all_slugs = list(set(positive_topics + negative_topics))

        # Validate topics exist
        stmt = select(Topic).where(Topic.slug.in_(all_slugs))
        result = await session.execute(stmt)
        found_topics = {t.slug: t for t in result.scalars().all()}

        missing_slugs = [slug for slug in all_slugs if slug not in found_topics]
        if missing_slugs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid topic slugs: {', '.join(missing_slugs)}",
            )

        updated_interests = []

        # Process positive topics
        for slug in positive_topics:
            topic = found_topics[slug]
            interest = await InterestService.set_user_interest(
                session=session,
                user_id=user_id,
                topic_slug=slug,
                interest_score=DEFAULT_SCORE,
                preference_type="POSITIVE",
                source="ONBOARDING",
            )
            updated_interests.append(interest)

        # Process negative topics
        for slug in negative_topics:
            topic = found_topics[slug]
            interest = await InterestService.set_user_interest(
                session=session,
                user_id=user_id,
                topic_slug=slug,
                interest_score=DEFAULT_SCORE,
                preference_type="NEGATIVE",
                source="ONBOARDING",
            )
            updated_interests.append(interest)

        return updated_interests

    @staticmethod
    async def update_interest_score(
        session: AsyncSession,
        user_id: uuid.UUID,
        topic_slug: str,
        new_score: float,
        source: str = "AGENT",
    ) -> Optional[UserInterest]:
        """
        Interface designed for future Interest Agent to dynamically modify scores.
        Clamps new_score to [0.0, 1.0].
        """
        clamped_score = max(0.0, min(1.0, new_score))

        stmt_topic = select(Topic).where(Topic.slug == topic_slug)
        result_topic = await session.execute(stmt_topic)
        topic = result_topic.scalar_one_or_none()
        if not topic:
            return None

        stmt_interest = select(UserInterest).where(
            UserInterest.user_id == user_id,
            UserInterest.topic_id == topic.id,
        )
        result_interest = await session.execute(stmt_interest)
        interest = result_interest.scalar_one_or_none()

        if not interest:
            return None

        interest.interest_score = clamped_score
        interest.source = source
        # Invalidate cached user interest embedding
        await session.execute(
            delete(UserInterestEmbedding).where(UserInterestEmbedding.user_id == user_id)
        )
        await session.commit()
        await session.refresh(interest, attribute_names=["topic"])
        return interest
