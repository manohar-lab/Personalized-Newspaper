"""behavior.py — Behavior Event Ingestion API Endpoint."""
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.learning.agent import InterestLearningAgent
from app.learning.schemas import BehaviorEventCreate, BehaviorEventResponse

router = APIRouter()


@router.post("/events", response_model=BehaviorEventResponse, status_code=status.HTTP_201_CREATED)
async def log_behavior_event(
    payload: BehaviorEventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record a user behavioral interaction (impressions, opens, reads, likes, saves, skips)."""
    agent = InterestLearningAgent(db)
    event = await agent.process_event(
        user_id=current_user.id,
        event_type=payload.event_type,
        article_id=payload.article_id,
        value=payload.value,
        metadata=payload.event_metadata,
        commit=True,
    )
    return event
