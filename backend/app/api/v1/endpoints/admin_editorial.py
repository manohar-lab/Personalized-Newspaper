"""admin_editorial.py — Phase 17 Protected Admin Editorial Debug API."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.newspaper_service import NewspaperService
from app.editorial.schemas import EditorialDebugResponse

router = APIRouter()


@router.get("/debug/{user_id}/{date}", response_model=EditorialDebugResponse, summary="Protected Editorial Debug Endpoint")
async def get_editorial_debug_log(
    user_id: uuid.UUID,
    date: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Protected development/admin endpoint returning complete editorial decision logs:
    candidate count, selected stories, excluded stories, section assignments, lead selection,
    and diversity decisions.
    """
    service = NewspaperService(db)
    try:
        return await service.get_editorial_debug(user_id=user_id, edition_date=date)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Editorial debug inspection error: {e}",
        )
