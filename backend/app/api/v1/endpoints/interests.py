from typing import List
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
    return format_interest_response(interest)


@router.put("", response_model=List[UserInterestResponse])
async def bulk_update_interests(
    payload: UpdateInterestsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple user interest preferences in a single request."""
    updated = []
    for item in payload.interests:
        interest = await InterestService.set_user_interest(
            session=db,
            user_id=current_user.id,
            topic_slug=item.topic_slug,
            interest_score=item.interest_score,
            preference_type=item.preference_type,
            source="USER_ACTION",
        )
        updated.append(format_interest_response(interest))
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
