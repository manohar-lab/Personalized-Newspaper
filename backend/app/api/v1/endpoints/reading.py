"""reading.py — Phase 12 Reading Session & Engagement Intelligence Endpoints."""
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.reading_service import ReadingService
from app.schemas.reading import (
    ReadingStartRequest,
    ReadingStartResponse,
    ReadingHeartbeatRequest,
    ReadingHeartbeatResponse,
    ReadingEndRequest,
    ReadingEndResponse,
    ReadingMetricsResponse,
)

router = APIRouter()


@router.post("/start", response_model=ReadingStartResponse, status_code=status.HTTP_201_CREATED)
async def start_reading_session(
    payload: ReadingStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a server-timestamped reading session and update aggregate reading history."""
    service = ReadingService(db)
    try:
        session_obj = await service.start_reading_session(
            user_id=current_user.id,
            article_id=payload.article_id,
            source_context=payload.source_context,
        )
        return ReadingStartResponse(
            session_id=session_obj.id,
            article_id=session_obj.article_id,
            started_at=session_obj.started_at,
            source_context=session_obj.source_context,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/heartbeat", response_model=ReadingHeartbeatResponse, status_code=status.HTTP_200_OK)
async def reading_heartbeat(
    payload: ReadingHeartbeatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Receive reading heartbeat with current scroll progress and tab visibility duration."""
    service = ReadingService(db)
    try:
        result = await service.record_heartbeat(
            user_id=current_user.id,
            session_id=payload.session_id,
            scroll_percentage=payload.scroll_percentage,
            active_duration_seconds=payload.active_duration_seconds,
        )
        return ReadingHeartbeatResponse(
            session_id=result["session_id"],
            is_active=result["is_active"],
            total_session_duration=result["total_session_duration"],
            max_scroll_percentage=result["max_scroll_percentage"],
            is_completed=result["is_completed"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/end", response_model=ReadingEndResponse, status_code=status.HTTP_200_OK)
async def end_reading_session(
    payload: ReadingEndRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Conclude active reading session, aggregate history, and feed Interest Learning Agent."""
    service = ReadingService(db)
    result = await service.end_reading_session(
        user_id=current_user.id,
        session_id=payload.session_id,
        article_id=payload.article_id,
        completion_percentage=payload.completion_percentage,
        max_scroll_percentage=payload.max_scroll_percentage,
    )
    return ReadingEndResponse(
        session_id=result["session_id"],
        article_id=result["article_id"],
        started_at=result["started_at"],
        ended_at=result["ended_at"],
        duration_seconds=result["duration_seconds"],
        completion_percentage=result["completion_percentage"],
        max_scroll_percentage=result["max_scroll_percentage"],
        engagement_score=result["engagement_score"],
        engagement_level=result["engagement_level"],
        is_completed=result["is_completed"],
    )


@router.get("/metrics", response_model=ReadingMetricsResponse, status_code=status.HTTP_200_OK)
async def get_reading_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get internal engagement intelligence development analytics."""
    service = ReadingService(db)
    metrics = await service.get_reading_metrics()
    return ReadingMetricsResponse(**metrics)

