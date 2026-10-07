"""profile_interests.py — Phase 19 Profile Interests & Behavioral Learning API Endpoints."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.learning.behavioral_engine import BehavioralLearningEngine
from app.learning.evidence_schemas import (
    ProfileRebuildResponse,
    RecordEvidenceRequest,
    TopicInterestItem,
    TopicOverrideRequest,
    UserProfileInterestsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["profile-interests"])


@router.get("/interests", response_model=UserProfileInterestsResponse)
async def get_user_interest_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the user's unified behavioral interest profile:
    - Strong interests (high engagement + confidence)
    - Growing interests (short-term rising topics)
    - Low engagement topics (respectfully classified)
    - Muted topics
    - Entity and keyword affinities
    - Active story affinities
    """
    engine = BehavioralLearningEngine(db)
    return await engine.get_user_unified_profile(current_user.id)


@router.post("/interests/override", response_model=TopicInterestItem)
async def apply_topic_preference_override(
    request: TopicOverrideRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Explicitly updates a topic preference (INCREASE, DECREASE, MUTE, UNMUTE, FOLLOW).
    Explicit preferences strictly override behavioral inferences.
    """
    engine = BehavioralLearningEngine(db)
    try:
        return await engine.apply_topic_override(current_user.id, request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Topic override failed for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to apply topic override")


@router.post("/rebuild", response_model=ProfileRebuildResponse)
async def rebuild_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Rebuilds the user's entire preference model deterministically from stored behavioral evidence.
    """
    engine = BehavioralLearningEngine(db)
    try:
        return await engine.rebuild_user_profile(current_user.id)
    except Exception as e:
        logger.error(f"Profile rebuild failed for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to rebuild profile")


@router.post("/evidence", status_code=status.HTTP_201_CREATED)
async def record_user_evidence(
    request: RecordEvidenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Records a raw behavioral evidence signal (OPEN, READ, COMPLETE, SAVE, LIKE, SEARCH, SKIP, etc.).
    """
    engine = BehavioralLearningEngine(db)
    ev = await engine.record_evidence(
        user_id=current_user.id,
        signal_type=request.signal_type,
        target_type=request.target_type,
        target_id=request.target_id,
        target_name=request.target_name,
        dwell_time_seconds=request.dwell_time_seconds,
        completion_ratio=request.completion_ratio,
        source_article_id=request.source_article_id,
        source_story_id=request.source_story_id,
        event_metadata=request.event_metadata,
        commit=True,
    )
    return {"status": "SUCCESS", "evidence_id": str(ev.id)}
