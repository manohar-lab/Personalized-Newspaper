"""briefings.py — Phase 18 Personal News Briefing API Endpoints."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user, get_optional_current_user
from app.models.user import User
from app.briefings.models import NewsBriefing
from app.briefings.engine import PersonalNewsBriefingEngine
from app.briefings.schemas import (
    BriefingHistorySummary,
    BriefingStatusResponse,
    GenerateBriefingRequest,
    NewsBriefingResponse,
)
from sqlalchemy import select, desc

router = APIRouter()


@router.get("/today", response_model=Optional[NewsBriefingResponse], summary="Get today's news briefing")
async def get_today_briefing(
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns today's news briefing snapshot.
    If unauthenticated, returns the latest published briefing or None.
    """
    engine = PersonalNewsBriefingEngine(db)
    if not current_user:
        stmt = (
            select(NewsBriefing)
            .where(NewsBriefing.status == "READY")
            .order_by(desc(NewsBriefing.briefing_date), desc(NewsBriefing.generated_at))
            .limit(1)
        )
        res = await db.execute(stmt)
        br = res.scalar_one_or_none()
        if br:
            return await engine._format_briefing_response(br)
        return None

    return await engine.get_today_briefing(current_user)


@router.get("/history", response_model=List[BriefingHistorySummary], summary="List past briefings history")
async def get_briefing_history(
    limit: int = Query(default=10, ge=1, le=50, description="Max historical briefings to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns a list of previous briefing summaries for the authenticated user."""
    engine = PersonalNewsBriefingEngine(db)
    return await engine.get_briefing_history(current_user.id, limit=limit)


@router.get("/{briefing_date}/status", response_model=BriefingStatusResponse, summary="Check status of a briefing")
async def get_briefing_status(
    briefing_date: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Checks whether the briefing for a specific date is ready or stale."""
    engine = PersonalNewsBriefingEngine(db)
    return await engine.get_briefing_status(current_user.id, briefing_date)


@router.get("/{briefing_date}", response_model=NewsBriefingResponse, summary="Get briefing snapshot for specific date")
async def get_briefing_by_date(
    briefing_date: str,
    version: Optional[int] = Query(default=None, description="Optional specific version number"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves a historical briefing snapshot for a given date."""
    engine = PersonalNewsBriefingEngine(db)
    briefing = await engine.get_briefing_by_date(current_user.id, briefing_date, version=version)
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No briefing found for user on date {briefing_date}",
        )
    return briefing


@router.post("/generate", response_model=NewsBriefingResponse, summary="Generate or refresh daily briefing")
async def generate_briefing(
    payload: GenerateBriefingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly triggers generation or refresh of a personalized briefing."""
    engine = PersonalNewsBriefingEngine(db)
    return await engine.generate_briefing(
        user_id=current_user.id,
        briefing_date=payload.briefing_date,
        daypart=payload.daypart,
        force_refresh=payload.force_refresh,
    )
