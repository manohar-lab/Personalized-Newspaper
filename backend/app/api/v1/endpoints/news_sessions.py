"""news_sessions.py — Phase 18 User News Session API Endpoints."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.briefings.session_service import NewsSessionService, ensure_utc, utc_now
from app.briefings.schemas import (
    EndSessionResponse,
    SessionHeartbeatRequest,
    SessionHeartbeatResponse,
    StartSessionRequest,
    StartSessionResponse,
)

router = APIRouter()


@router.post("/start", response_model=StartSessionResponse, summary="Start a news reading session")
async def start_news_session(
    payload: Optional[StartSessionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Initializes a new reading session for the user."""
    service = NewsSessionService(db)
    sess = await service.start_session(current_user.id)
    return StartSessionResponse(
        session_id=sess.id,
        started_at=sess.started_at,
    )


@router.post("/{session_id}/heartbeat", response_model=SessionHeartbeatResponse, summary="Record session heartbeat and activity")
async def session_heartbeat(
    session_id: uuid.UUID,
    payload: SessionHeartbeatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pings a heartbeat to keep the session alive and record activity."""
    service = NewsSessionService(db)
    sess = await service.record_heartbeat(
        session_id=session_id,
        user_id=current_user.id,
        stories_viewed_delta=payload.stories_viewed_delta,
        articles_opened_delta=payload.articles_opened_delta,
        has_meaningful_activity=payload.has_meaningful_activity,
    )
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or belongs to another user.",
        )
    return SessionHeartbeatResponse(
        session_id=sess.id,
        is_active=(sess.ended_at is None),
        last_heartbeat_at=sess.last_heartbeat_at,
    )


@router.post("/{session_id}/end", response_model=EndSessionResponse, summary="End a news reading session")
async def end_news_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Closes an active news session and calculates engagement duration."""
    service = NewsSessionService(db)
    sess = await service.end_session(session_id, current_user.id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or belongs to another user.",
        )

    started_dt = ensure_utc(sess.started_at) or utc_now()
    ended_dt = ensure_utc(sess.ended_at) or utc_now()
    duration = (ended_dt - started_dt).total_seconds()

    return EndSessionResponse(
        session_id=sess.id,
        started_at=sess.started_at,
        ended_at=sess.ended_at,
        duration_seconds=max(0.0, duration),
        stories_viewed=sess.stories_viewed,
        articles_opened=sess.articles_opened,
        meaningful_activity=sess.meaningful_activity,
    )
