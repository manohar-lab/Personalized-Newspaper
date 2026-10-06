"""sources.py — Phase 15 News Source Management & Intelligence API Endpoints."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_

from app.database.session import get_db
from app.api.deps import get_current_user, get_optional_current_user
from app.models.user import User
from app.models.source import NewsSource
from app.models.article import Article
from app.source_intelligence.source_evaluator import SourceEvaluationService
from app.source_intelligence.schemas import (
    SourceItem,
    SourceDetail,
    SourceListResponse,
    SourceReportRequest,
)

router = APIRouter()


@router.get("", response_model=SourceListResponse)
async def list_sources(
    search: Optional[str] = Query(None, description="Search source by name or description"),
    status: Optional[str] = Query(None, description="Filter by health_status: HEALTHY | DEGRADED | FAILING | INACTIVE"),
    following_only: bool = Query(False, description="Filter by sources followed by user"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists news sources with health status, article counts, and follow/mute preferences."""
    eval_service = SourceEvaluationService(db)

    followed_ids = []
    muted_ids = []
    if current_user:
        followed_ids, muted_ids = await eval_service.get_user_source_preferences(current_user.id)

    query = select(NewsSource)

    if search:
        s_term = f"%{search.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(NewsSource.name).like(s_term),
                func.lower(NewsSource.description).like(s_term),
            )
        )

    if status:
        query = query.where(NewsSource.health_status == status.upper())

    if following_only and current_user:
        query = query.where(NewsSource.id.in_(followed_ids))

    # Count total
    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    stmt_paged = query.order_by(desc(NewsSource.quality_score), NewsSource.name).offset(offset).limit(limit)
    res = await db.execute(stmt_paged)
    sources = res.scalars().all()

    items = []
    for s in sources:
        stmt_art_count = select(func.count(Article.id)).where(Article.source_id == s.id)
        art_count = (await db.execute(stmt_art_count)).scalar() or 0

        items.append(
            SourceItem(
                id=s.id,
                name=s.name,
                slug=s.slug,
                website_url=s.website_url,
                description=s.description,
                logo_url=s.logo_url,
                is_active=s.is_active,
                health_status=s.health_status or "HEALTHY",
                freshness_score=s.freshness_score or 0.50,
                quality_score=s.quality_score or 0.50,
                quality_confidence=s.quality_confidence or 0.05,
                reliability_score=s.reliability_score or 0.50,
                coverage_score=s.coverage_score or 0.50,
                extraction_success_rate=s.extraction_success_rate or 1.0,
                duplicate_rate=s.duplicate_rate or 0.0,
                article_count=art_count,
                is_following=s.id in followed_ids,
                is_muted=s.id in muted_ids,
                last_evaluated_at=s.last_evaluated_at,
            )
        )

    return SourceListResponse(
        sources=items,
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{source_id}", response_model=SourceDetail)
async def get_source_detail(
    source_id: uuid.UUID = Path(..., description="Source UUID"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get rich detail for a news source including recent articles and coverage topics."""
    eval_service = SourceEvaluationService(db)
    user_id = current_user.id if current_user else None
    detail = await eval_service.get_source_detail(source_id=source_id, user_id=user_id)
    if not detail:
        raise HTTPException(status_code=404, detail="News source not found")
    return detail


@router.post("/{source_id}/follow", status_code=status.HTTP_200_OK)
async def follow_source(
    source_id: uuid.UUID = Path(..., description="Source UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Follow a news source to prioritize its articles in recommendations and newspaper."""
    eval_service = SourceEvaluationService(db)
    await eval_service.follow_source(user_id=current_user.id, source_id=source_id)
    return {"status": "success", "message": "Source followed successfully"}


@router.delete("/{source_id}/follow", status_code=status.HTTP_200_OK)
async def unfollow_source(
    source_id: uuid.UUID = Path(..., description="Source UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unfollow a news source."""
    eval_service = SourceEvaluationService(db)
    await eval_service.unfollow_source(user_id=current_user.id, source_id=source_id)
    return {"status": "success", "message": "Source unfollowed successfully"}


@router.post("/{source_id}/mute", status_code=status.HTTP_200_OK)
async def mute_source(
    source_id: uuid.UUID = Path(..., description="Source UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mute a news source to exclude its articles from recommendations and newspaper."""
    eval_service = SourceEvaluationService(db)
    await eval_service.mute_source(user_id=current_user.id, source_id=source_id)
    return {"status": "success", "message": "Source muted successfully"}


@router.delete("/{source_id}/mute", status_code=status.HTTP_200_OK)
async def unmute_source(
    source_id: uuid.UUID = Path(..., description="Source UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unmute a previously muted news source."""
    eval_service = SourceEvaluationService(db)
    await eval_service.unmute_source(user_id=current_user.id, source_id=source_id)
    return {"status": "success", "message": "Source unmuted successfully"}


@router.post("/{source_id}/report", status_code=status.HTTP_201_CREATED)
async def report_source(
    req: SourceReportRequest,
    source_id: uuid.UUID = Path(..., description="Source UUID"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Report an issue regarding a source (e.g. MISLEADING, LOW_QUALITY, PAYWALL, BROKEN_ARTICLE)."""
    eval_service = SourceEvaluationService(db)
    user_id = current_user.id if current_user else None
    report = await eval_service.report_source(
        source_id=source_id,
        reason=req.reason,
        details=req.details,
        user_id=user_id,
    )
    return {"status": "success", "report_id": str(report.id), "message": "Report submitted for review"}
