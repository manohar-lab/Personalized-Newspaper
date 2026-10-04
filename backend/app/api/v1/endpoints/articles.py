import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, status
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
