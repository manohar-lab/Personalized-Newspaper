"""reading.py — Reading Session Tracking API Endpoints."""
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.learning.agent import InterestLearningAgent
from app.learning.schemas import (
    ReadingStartRequest,
    ReadingStartResponse,
    ReadingEndRequest,
    ReadingEndResponse,
)

router = APIRouter()


@router.post("/start", response_model=ReadingStartResponse, status_code=status.HTTP_201_CREATED)
async def start_reading_session(
    payload: ReadingStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a reading session for an article."""
    agent = InterestLearningAgent(db)
    session_obj = await agent.start_reading_session(
        user_id=current_user.id,
        article_id=payload.article_id,
    )
    return ReadingStartResponse(
        session_id=session_obj.id,
        article_id=session_obj.article_id,
        started_at=session_obj.started_at,
    )


@router.post("/end", response_model=ReadingEndResponse, status_code=status.HTTP_200_OK)
async def end_reading_session(
    payload: ReadingEndRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Conclude an active reading session and calculate completion metrics."""
    agent = InterestLearningAgent(db)
    session_obj = await agent.end_reading_session(
        session_id=payload.session_id,
        user_id=current_user.id,
        article_id=payload.article_id,
        completion_percentage=payload.completion_percentage,
    )
    return ReadingEndResponse(
        session_id=session_obj.id,
        article_id=session_obj.article_id,
        started_at=session_obj.started_at,
        ended_at=session_obj.ended_at or session_obj.started_at,
        duration_seconds=session_obj.duration_seconds or 0.0,
        completion_percentage=session_obj.completion_percentage or 0.0,
    )
