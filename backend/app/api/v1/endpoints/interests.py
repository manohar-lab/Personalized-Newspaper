import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.schemas.interest import (
    UserInterestItem,
    UserInterestResponse,
    UpdateInterestsRequest,
)
from app.services.interest_service import InterestService
from app.learning.agent import InterestLearningAgent
from app.learning.schemas import UserLearningProfileResponse
from app.ai.interests.learner import InterestLearningService
from app.ai.interests.schemas import (
    DynamicProfileResponse,
    UpdateTopicPreferenceRequest,
    ResetLearnedProfileResponse,
    RelevanceExplanationResponse,
)

router = APIRouter()

def format_interest_response(interest) -> UserInterestResponse:
    return UserInterestResponse(
        id=interest.id,
        topic_slug=interest.topic.slug,
        topic_name=interest.topic.name,
        interest_score=interest.interest_score,
        preference_type=interest.preference_type,
        source=interest.source,
        created_at=interest.created_at,
        updated_at=interest.updated_at,
    )

@router.get("/dynamic-profile", response_model=DynamicProfileResponse)
async def get_dynamic_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Phase 13: Retrieve user's dynamic interest intelligence profile (explicit, strong, emerging, avoided, etc.)."""
    learner = InterestLearningService(db)
    return await learner.get_dynamic_profile(current_user.id)


@router.get("/profile", response_model=UserLearningProfileResponse)
async def get_learning_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve explicit vs learned user interest profile with entities and keywords."""
    agent = InterestLearningAgent(db)
    return await agent.get_user_learning_profile(current_user.id)


@router.post("/preferences", status_code=status.HTTP_200_OK)
async def update_topic_preference(
    payload: UpdateTopicPreferenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set positive, negative, or neutral preference for a topic."""
    learner = InterestLearningService(db)
    pref = await learner.set_topic_preference(
        user_id=current_user.id,
        topic_id=payload.topic_id,
        preference=payload.preference,
        strength=payload.strength or 1.0,
    )
    return {
        "status": "success",
        "topic_id": str(pref.topic_id),
        "preference": pref.preference,
        "strength": pref.strength,
    }


@router.delete("/learned/{topic_id}", status_code=status.HTTP_200_OK)
async def remove_learned_interest(
    topic_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a specific learned or inferred topic interest."""
    learner = InterestLearningService(db)
    removed = await learner.remove_learned_interest(current_user.id, topic_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learned topic interest not found",
        )
    return {"status": "success", "message": "Learned interest removed."}


@router.post("/reset-learned", response_model=ResetLearnedProfileResponse)
async def reset_learned_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset all learned and inferred interests while strictly preserving explicit user interests."""
    learner = InterestLearningService(db)
    preserved = await learner.reset_learned_profile(current_user.id)
    return ResetLearnedProfileResponse(
        status="success",
        message="Learned profile reset successfully. Explicit interests were preserved.",
        explicit_interests_preserved=preserved,
    )


@router.get("/explanation/{article_id}", response_model=RelevanceExplanationResponse)
async def explain_article_relevance(
    article_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Produce human-readable explanation of why an article was curated for the current user."""
    learner = InterestLearningService(db)
    return await learner.explain_article_relevance(current_user.id, article_id)


@router.get("", response_model=List[UserInterestResponse])
async def get_my_interests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the current user's interest preferences."""
    interests = await InterestService.get_user_interests(db, current_user.id)
    return [format_interest_response(i) for i in interests]


@router.post("", response_model=UserInterestResponse, status_code=status.HTTP_201_CREATED)
async def add_or_update_interest(
    item: UserInterestItem,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add or update an interest preference for a single topic."""
    interest = await InterestService.set_user_interest(
        session=db,
        user_id=current_user.id,
        topic_slug=item.topic_slug,
        interest_score=item.interest_score,
        preference_type=item.preference_type,
        source="USER_ACTION",
    )
    # Also sync Phase 13 explicit interest profile
    learner = InterestLearningService(db)
    await learner.sync_explicit_interest(
        user_id=current_user.id,
        topic_id=interest.topic_id,
        score=interest.interest_score,
    )
    await db.commit()
    return format_interest_response(interest)


@router.put("", response_model=List[UserInterestResponse])
async def bulk_update_interests(
    payload: UpdateInterestsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple user interest preferences in a single request."""
    updated = []
    learner = InterestLearningService(db)
    for item in payload.interests:
        interest = await InterestService.set_user_interest(
            session=db,
            user_id=current_user.id,
            topic_slug=item.topic_slug,
            interest_score=item.interest_score,
            preference_type=item.preference_type,
            source="USER_ACTION",
        )
        await learner.sync_explicit_interest(
            user_id=current_user.id,
            topic_id=interest.topic_id,
            score=interest.interest_score,
        )
        updated.append(format_interest_response(interest))
    await db.commit()
    return updated


@router.delete("/{topic_slug}", status_code=status.HTTP_200_OK)
async def remove_interest(
    topic_slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove user preference for a specified topic slug."""
    removed = await InterestService.remove_user_interest(
        session=db,
        user_id=current_user.id,
        topic_slug=topic_slug,
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No interest preference found for topic '{topic_slug}'",
        )
    return {"message": f"Interest for topic '{topic_slug}' successfully removed."}

