import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.api.deps import get_current_user, get_optional_current_user
from app.models.user import User
from app.services.article_service import ArticleService
from app.services.action_service import ActionService
from app.schemas.article import (
    ArticleBase,
    ArticleDetailResponse,
    ArticleListResponse,
)
from app.schemas.action import UserActionResponse
from app.schemas.reading import (
    ReadingHistoryItemResponse,
    ArticleReadingStateResponse,
    ReadingStartResponse,
    ReadingHeartbeatResponse,
    ReadingEndResponse,
)

router = APIRouter()

@router.get("", response_model=ArticleListResponse)
async def list_articles(
    topic: Optional[str] = Query(None, description="Topic slug to filter by"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List published articles with optional topic filter and pagination."""
    service = ArticleService(db)
    return await service.get_published_articles(
        topic_slug=topic, page=page, limit=limit, current_user=current_user
    )

@router.get("/featured", response_model=ArticleBase)
async def get_featured_article(
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest featured published article."""
    service = ArticleService(db)
    return await service.get_featured_article(current_user=current_user)

@router.get("/topics/{topic_slug}", response_model=ArticleListResponse)
async def list_articles_by_topic(
    topic_slug: str = Path(..., description="Topic slug"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List published articles belonging to a specific topic slug."""
    service = ArticleService(db)
    return await service.get_published_articles(
        topic_slug=topic_slug, page=page, limit=limit, current_user=current_user
    )

@router.get("/{id}", response_model=ArticleDetailResponse)
async def get_article_detail(
    id: uuid.UUID = Path(..., description="Article UUID"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full editorial article details and related articles."""
    service = ArticleService(db)
    return await service.get_article_detail(article_id=id, current_user=current_user)

@router.post("/{id}/save", response_model=UserActionResponse, status_code=status.HTTP_200_OK)
async def save_article(
    id: uuid.UUID = Path(..., description="Article UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save an article to current user's saved list."""
    service = ActionService(db)
    return await service.save_article(user_id=current_user.id, article_id=id)

@router.delete("/{id}/save", response_model=UserActionResponse, status_code=status.HTTP_200_OK)
async def unsave_article(
    id: uuid.UUID = Path(..., description="Article UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove an article from current user's saved list."""
    service = ActionService(db)
    return await service.unsave_article(user_id=current_user.id, article_id=id)

@router.post("/{id}/like", response_model=UserActionResponse, status_code=status.HTTP_200_OK)
async def like_article(
    id: uuid.UUID = Path(..., description="Article UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Like an article."""
    service = ActionService(db)
    return await service.like_article(user_id=current_user.id, article_id=id)

@router.delete("/{id}/like", response_model=UserActionResponse, status_code=status.HTTP_200_OK)
async def unlike_article(
    id: uuid.UUID = Path(..., description="Article UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove like from an article."""
    service = ActionService(db)
    await service.action_repo.remove_action(
        user_id=current_user.id, article_id=id, action="LIKE"
    )
    return UserActionResponse(
        success=True,
        action="LIKE",
        article_id=id,
        message="Like removed",
    )

@router.post("/{id}/not-interested", response_model=UserActionResponse, status_code=status.HTTP_200_OK)
async def mark_not_interested(
    id: uuid.UUID = Path(..., description="Article UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark an article as not interested."""
    service = ActionService(db)
    return await service.mark_not_interested(user_id=current_user.id, article_id=id)


@router.get("/{id}/reading-history", response_model=Optional[ReadingHistoryItemResponse])
async def get_article_reading_history(
    id: uuid.UUID = Path(..., description="Article UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get authenticated user's private reading history for this article."""
    from app.services.reading_service import ReadingService
    service = ReadingService(db)
    history = await service.get_article_reading_history(user_id=current_user.id, article_id=id)
    if not history:
        raise HTTPException(status_code=404, detail="Reading history for this article not found")
    return history


@router.get("/{id}/recommendations")
async def get_article_recommendations(
    id: uuid.UUID = Path(..., description="Article UUID"),
    limit: int = Query(6, ge=1, le=20),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get 'More like this' recommendations based on target article embedding & topic overlap."""
    from app.recommendations.recommendation_service import RecommendationService
    service = RecommendationService(db)
    user_id = current_user.id if current_user else uuid.uuid4()
    return await service.get_more_like_this(user_id=user_id, article_id=id, limit=limit)


@router.get("/{id}/coverage")
async def get_article_coverage(
    id: uuid.UUID = Path(..., description="Article UUID"),
    db: AsyncSession = Depends(get_db),
):
    """Get multi-perspective story cluster coverage, syndication analysis, and conflict flags."""
    from app.source_intelligence.source_evaluator import SourceEvaluationService
    eval_service = SourceEvaluationService(db)
    return await eval_service.get_story_coverage(article_id=id)


@router.get("/{id}/reading-state", response_model=ArticleReadingStateResponse)
async def get_article_reading_state(
    id: uuid.UUID = Path(..., description="Article UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get concise reading state for progress indicator and resume reading."""
    from app.services.reading_service import ReadingService
    service = ReadingService(db)
    return await service.get_reading_state(user_id=current_user.id, article_id=id)


@router.post("/{id}/reading/start", response_model=ReadingStartResponse, status_code=status.HTTP_201_CREATED)
async def start_reading(
    id: uuid.UUID = Path(..., description="Article UUID"),
    source_context: Optional[str] = Query("DIRECT", description="Source context: NEWSPAPER | SEARCH | SAVED | DIRECT | OTHER"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start an active reading session for this article."""
    from app.services.reading_service import ReadingService
    service = ReadingService(db)
    session_obj = await service.start_reading_session(
        user_id=current_user.id, article_id=id, source_context=source_context
    )
    return ReadingStartResponse(
        session_id=session_obj.id,
        article_id=session_obj.article_id,
        started_at=session_obj.started_at,
        source_context=session_obj.source_context,
    )


@router.post("/{id}/reading/progress", response_model=ReadingHeartbeatResponse, status_code=status.HTTP_200_OK)
async def report_reading_progress(
    id: uuid.UUID = Path(..., description="Article UUID"),
    session_id: uuid.UUID = Query(..., description="Active ReadingSession UUID"),
    scroll_percentage: float = Query(..., ge=0.0, le=100.0, description="Current scroll percentage"),
    active_duration_seconds: Optional[float] = Query(None, ge=0.0, description="Active duration in seconds"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Report periodic reading heartbeat / scroll progress."""
    from app.services.reading_service import ReadingService
    service = ReadingService(db)
    return await service.record_heartbeat(
        user_id=current_user.id,
        session_id=session_id,
        scroll_percentage=scroll_percentage,
        active_duration_seconds=active_duration_seconds,
    )


@router.post("/{id}/reading/complete", response_model=ReadingEndResponse, status_code=status.HTTP_200_OK)
async def complete_reading(
    id: uuid.UUID = Path(..., description="Article UUID"),
    session_id: uuid.UUID = Query(..., description="Active ReadingSession UUID"),
    completion_percentage: Optional[float] = Query(None, ge=0.0, le=100.0),
    max_scroll_percentage: Optional[float] = Query(None, ge=0.0, le=100.0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Finalize reading session and deliver behavioral engagement signals."""
    from app.services.reading_service import ReadingService
    service = ReadingService(db)
    return await service.end_reading_session(
        user_id=current_user.id,
        session_id=session_id,
        article_id=id,
        completion_percentage=completion_percentage,
        max_scroll_percentage=max_scroll_percentage,
    )


@router.post("/{id}/report", status_code=status.HTTP_201_CREATED)
async def report_article(
    id: uuid.UUID = Path(..., description="Article UUID"),
    reason: str = Query(..., description="MISLEADING | LOW_QUALITY | BROKEN_ARTICLE | DUPLICATE | PAYWALL | OTHER"),
    details: Optional[str] = Query(None, description="Optional details or context"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit quality/accuracy/paywall feedback report for an article."""
    from app.source_intelligence.source_evaluator import SourceEvaluationService
    eval_service = SourceEvaluationService(db)
    user_id = current_user.id if current_user else None
    report = await eval_service.report_article(
        article_id=id,
        reason=reason,
        details=details,
        user_id=user_id,
    )
    return {"status": "success", "report_id": str(report.id), "message": "Article report recorded"}



