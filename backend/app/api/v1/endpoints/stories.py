"""stories.py — Phase 16 Multi-Source Story Intelligence API Endpoints."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_optional_current_user, get_current_user
from app.models.user import User
from app.story_intelligence.story_service import StoryIntelligenceService
from app.story_intelligence.schemas import (
    StoryFeedResponse,
    StoryDetail,
    StoryTimelineItem,
    StoryCoverageResponse,
    StoryItem,
    StorySearchResponse,
    StoryMergeRequest,
)

router = APIRouter()


@router.get("", response_model=StoryFeedResponse, summary="List multi-source developing and active stories")
async def list_stories(
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, DEVELOPING, STABLE, RESOLVED, ARCHIVED"),
    topic: Optional[str] = Query(None, description="Filter by topic name or slug"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    service = StoryIntelligenceService(db)
    user_id = current_user.id if current_user else None
    return await service.get_stories_feed(
        status=status,
        topic=topic,
        page=page,
        limit=limit,
        user_id=user_id,
    )


@router.get("/search", response_model=StorySearchResponse, summary="Intelligent multi-source story search")
async def search_stories(
    q: str = Query("", description="Search query string"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    status: Optional[str] = Query(None, description="Filter by story status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    service = StoryIntelligenceService(db)
    return await service.search_stories(
        query=q,
        topic=topic,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{story_id_or_slug}", response_model=StoryDetail, summary="Get full story details and metadata")
async def get_story_detail(
    story_id_or_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    service = StoryIntelligenceService(db)
    user_id = current_user.id if current_user else None
    story = await service.get_story_detail(story_id_or_slug, user_id=user_id)
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    return story


@router.get("/{story_id_or_slug}/timeline", response_model=list[StoryTimelineItem], summary="Get chronological story timeline")
async def get_story_timeline(
    story_id_or_slug: str,
    db: AsyncSession = Depends(get_db),
):
    service = StoryIntelligenceService(db)
    return await service.get_story_timeline(story_id_or_slug)


@router.get("/{story_id_or_slug}/coverage", response_model=StoryCoverageResponse, summary="Get multi-source coverage breakdown")
async def get_story_coverage(
    story_id_or_slug: str,
    db: AsyncSession = Depends(get_db),
):
    service = StoryIntelligenceService(db)
    coverage = await service.get_story_coverage(story_id_or_slug)
    if not coverage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )
    return coverage


@router.get("/{story_id_or_slug}/related", response_model=list[StoryItem], summary="Get related stories")
async def get_related_stories(
    story_id_or_slug: str,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    service = StoryIntelligenceService(db)
    return await service.get_related_stories(story_id_or_slug, limit=limit)


@router.post("/merge", response_model=StoryDetail, summary="Merge two evolving duplicate stories")
async def merge_stories(
    payload: StoryMergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = StoryIntelligenceService(db)
    try:
        merged_story = await service.merge_stories(
            source_story_id=payload.source_story_id,
            target_story_id=payload.target_story_id,
            reason=payload.reason,
        )
        await db.commit()
        return await service.get_story_detail(str(merged_story.id))
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
