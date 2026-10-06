from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.action_service import ActionService
from app.services.reading_service import ReadingService
from app.schemas.action import SavedArticlesListResponse
from app.schemas.reading import (
    ReadingHistoryListResponse,
    ReadingHistoryItemResponse,
    ContinueReadingListResponse,
    ContinueReadingItemResponse,
)

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


@router.get("/reading-history", response_model=ReadingHistoryListResponse)
async def get_my_reading_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Optional alias for page_size"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated private reading history for the authenticated user."""
    effective_page_size = limit if limit is not None else page_size
    service = ReadingService(db)
    items, total = await service.get_user_reading_history(
        user_id=current_user.id, page=page, page_size=effective_page_size
    )
    total_pages = max(1, (total + effective_page_size - 1) // effective_page_size) if total > 0 else 1
    return ReadingHistoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=effective_page_size,
        total_pages=total_pages,
    )


@router.get("/continue-reading", response_model=ContinueReadingListResponse)
async def get_my_continue_reading(
    limit: int = Query(10, ge=1, le=50, description="Max items to retrieve"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get articles user started but hasn't completed yet for quick resumption."""
    service = ReadingService(db)
    histories = await service.get_continue_reading(
        user_id=current_user.id, limit=limit
    )
    items = [
        ContinueReadingItemResponse(
            article_id=h.article_id,
            article=h.article,
            last_read_at=h.last_read_at,
            progress_percentage=h.last_completion_percentage,
            max_scroll_percentage=h.max_scroll_percentage,
            total_duration_seconds=h.total_duration_seconds,
            engagement_level=h.engagement_level,
        )
        for h in histories
    ]
    return ContinueReadingListResponse(items=items, total=len(items))


@router.delete("/reading-history", status_code=status.HTTP_200_OK)
async def clear_my_reading_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear reading history for the authenticated user."""
    from sqlalchemy import delete
    from app.models.reading_history import ReadingHistory
    from app.learning.models import ReadingSession

    await db.execute(delete(ReadingSession).where(ReadingSession.user_id == current_user.id))
    await db.execute(delete(ReadingHistory).where(ReadingHistory.user_id == current_user.id))
    await db.commit()
    return {"success": True, "message": "Reading history cleared successfully."}

