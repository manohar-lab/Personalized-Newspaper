from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.action_service import ActionService
from app.schemas.action import SavedArticlesListResponse

router = APIRouter()

@router.get("/saved-articles", response_model=SavedArticlesListResponse)
async def get_saved_articles(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get list of saved articles for the authenticated user."""
    service = ActionService(db)
    return await service.get_saved_articles(
        user_id=current_user.id, page=page, limit=limit
    )
