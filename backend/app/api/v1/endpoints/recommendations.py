"""recommendations.py — Recommendations API Endpoints."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.session import get_db
from app.api.deps import get_current_user, get_optional_current_user
from app.models.user import User
from app.recommendations.recommendation_service import RecommendationService
from app.recommendations.schemas import (
    RecommendationFeedResponse,
    TrendingForYouResponse,
    MoreLikeThisResponse,
    RecommendationInteractionRequest,
)

router = APIRouter()


@router.get("", response_model=RecommendationFeedResponse)
async def get_recommendations(
    limit: int = Query(20, ge=1, le=50),
    page: int = Query(1, ge=1),
    context: str = Query("DISCOVER"),
    force_refresh: bool = Query(False),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve personalized news discovery & recommendations feed."""
    service = RecommendationService(db)

    user_id = current_user.id if current_user else None
    if not user_id:
        # Fetch first active user or fallback user
        stmt = select(User.id).where(User.is_active.is_(True)).limit(1)
        res = await db.execute(stmt)
        user_id = res.scalar_one_or_none()
        if not user_id:
            user_id = uuid.uuid4()

    try:
        return await service.recommend(
            user_id=user_id,
            limit=limit,
            context=context,
            page=page,
            force_refresh=force_refresh,
        )
    except Exception as e:
        # Graceful fallback: return recent articles if personalization error occurs
        stmt_fallback = select(User.id).where(User.is_active.is_(True)).limit(1)
        res_fb = await db.execute(stmt_fallback)
        fallback_uid = res_fb.scalar_one_or_none() or uuid.uuid4()
        return await service.recommend(
            user_id=fallback_uid,
            limit=limit,
            context=context,
            page=page,
            force_refresh=True,
        )


@router.get("/trending-for-you", response_model=TrendingForYouResponse)
async def get_trending_for_you(
    limit: int = Query(10, ge=1, le=30),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve top trending stories aligned with user's preferred topics."""
    service = RecommendationService(db)
    user_id = current_user.id if current_user else None
    if not user_id:
        stmt = select(User.id).where(User.is_active.is_(True)).limit(1)
        res = await db.execute(stmt)
        user_id = res.scalar_one_or_none() or uuid.uuid4()

    return await service.get_trending_for_you(user_id=user_id, limit=limit)


@router.post("/interactions", status_code=status.HTTP_200_OK)
async def record_recommendation_interaction(
    payload: RecommendationInteractionRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record recommendation impression (IMPRESSION) or click (CLICK)."""
    service = RecommendationService(db)
    user_id = current_user.id if current_user else None
    if not user_id:
        stmt = select(User.id).where(User.is_active.is_(True)).limit(1)
        res = await db.execute(stmt)
        user_id = res.scalar_one_or_none() or uuid.uuid4()

    await service.record_interaction(
        user_id=user_id,
        article_id=payload.article_id,
        interaction_type=payload.interaction_type,
        context=payload.context,
    )
    return {"status": "success", "article_id": payload.article_id, "interaction": payload.interaction_type}
