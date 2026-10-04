from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.schemas.interest import OnboardingInterestsRequest, UserInterestResponse
from app.services.interest_service import InterestService

router = APIRouter()

@router.post("/interests", response_model=List[UserInterestResponse], status_code=status.HTTP_201_CREATED)
async def submit_onboarding_interests(
    payload: OnboardingInterestsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit initial onboarding interests (positive and negative topics).
    Validates topics and initializes initial preference scores.
    """
    interests = await InterestService.initialize_onboarding_interests(
        session=db,
        user_id=current_user.id,
        positive_topics=payload.positive_topics,
        negative_topics=payload.negative_topics,
    )
    return [
        UserInterestResponse(
            id=i.id,
            topic_slug=i.topic.slug,
            topic_name=i.topic.name,
            interest_score=i.interest_score,
            preference_type=i.preference_type,
            source=i.source,
            created_at=i.created_at,
            updated_at=i.updated_at,
        )
        for i in interests
    ]
