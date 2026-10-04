from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.newspaper_service import NewspaperService
from app.schemas.newspaper import NewspaperResponse

router = APIRouter()

@router.get("", response_model=NewspaperResponse)
async def get_personalized_newspaper(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the personalized newspaper edition for the authenticated user.
    Uses user's interest topics and preference scores to rank and curate sections.
    """
    service = NewspaperService(db)
    return await service.get_personalized_newspaper(user=current_user)
