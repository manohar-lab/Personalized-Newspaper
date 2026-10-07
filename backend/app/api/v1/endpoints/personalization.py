"""personalization.py — Phase 23 Personalization Control Center & Transparency API Endpoints."""
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Path, Body
from sqlalchemy import select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.topic import Topic
from app.models.interest import UserInterest
from app.schemas.personalization import (
    PersonalizationSettingsResponse,
    PersonalizationSettingsUpdate,
    ExplicitInterestItem,
    PersonalizationProfileResponse,
    WhyThisStoryResponse,
    TopicControlItem,
    EntityControlItem,
    SourceControlItem,
)
from app.personalization.services.control_center_service import PersonalizationControlCenterService

router = APIRouter()


@router.get("/profile", response_model=PersonalizationProfileResponse, summary="Get full personalization control center profile")
async def get_personalization_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full transparent profile: explicit interests, inferred topics, entities, sources, settings, stats."""
    service = PersonalizationControlCenterService(db)
    return await service.get_personalization_profile(current_user.id)


@router.get("/settings", response_model=PersonalizationSettingsResponse, summary="Get personalization settings")
async def get_personalization_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get discovery level, personalization strength, diversity level, and learning state."""
    service = PersonalizationControlCenterService(db)
    settings_obj = await service.get_or_create_settings(current_user.id)
    return PersonalizationSettingsResponse.model_validate(settings_obj)


@router.put("/settings", response_model=PersonalizationSettingsResponse, summary="Update personalization settings")
async def update_personalization_settings(
    update_data: PersonalizationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update personalization tuning parameters."""
    service = PersonalizationControlCenterService(db)
    settings_obj = await service.update_settings(current_user.id, update_data)
    return PersonalizationSettingsResponse.model_validate(settings_obj)


@router.get("/interests", response_model=List[ExplicitInterestItem], summary="Get explicit interests")
async def get_explicit_interests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get directly selected user interests."""
    stmt = (
        select(UserInterest)
        .options(selectinload(UserInterest.topic))
        .where(UserInterest.user_id == current_user.id, UserInterest.preference_type == "POSITIVE")
    )
    res = await db.execute(stmt)
    rows = list(res.scalars().all())
    return [
        ExplicitInterestItem(
            id=r.id,
            topic_id=r.topic_id,
            topic_name=r.topic.name if r.topic else "General",
            topic_slug=r.topic.slug if r.topic else "general",
            preference_type=r.preference_type,
            interest_score=r.interest_score,
            source=r.source,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/interests", summary="Add explicit interest")
async def add_explicit_interest(
    topic_id: uuid.UUID = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a topic to explicit user interests."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_topic(current_user.id, topic_id, "FOLLOW")


@router.delete("/interests/{id}", summary="Remove explicit interest")
async def delete_explicit_interest(
    id: uuid.UUID = Path(..., description="UserInterest UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a topic from explicit interests."""
    stmt = select(UserInterest).where(UserInterest.id == id, UserInterest.user_id == current_user.id)
    res = await db.execute(stmt)
    ui = res.scalar_one_or_none()
    if not ui:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interest not found")
    await db.delete(ui)
    await db.commit()
    return {"status": "SUCCESS", "message": "Interest removed"}


@router.get("/topics/search", summary="Search available topics with hierarchy")
async def search_topics(
    q: str = Query("", description="Search term for topics"),
    db: AsyncSession = Depends(get_db),
):
    """Search topics with parent topic hierarchy."""
    stmt = select(Topic).options(selectinload(Topic.parent_topic))
    if q.strip():
        stmt = stmt.where(Topic.name.ilike(f"%{q.strip()}%"))
    stmt = stmt.order_by(Topic.name).limit(30)
    res = await db.execute(stmt)
    topics = list(res.scalars().all())
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "slug": t.slug,
            "parent_id": str(t.parent_topic_id) if t.parent_topic_id else None,
            "parent_name": t.parent_topic.name if getattr(t, "parent_topic", None) else None,
        }
        for t in topics
    ]


@router.post("/topics/{id}/follow", summary="Follow topic")
async def follow_topic(
    id: uuid.UUID = Path(..., description="Topic UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Follow a topic explicitly."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_topic(current_user.id, id, "FOLLOW")


@router.post("/topics/{id}/mute", summary="Mute topic")
async def mute_topic(
    id: uuid.UUID = Path(..., description="Topic UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mute a topic explicitly."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_topic(current_user.id, id, "MUTE")


@router.post("/topics/{id}/unmute", summary="Unmute topic")
async def unmute_topic(
    id: uuid.UUID = Path(..., description="Topic UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unmute a previously muted topic."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_topic(current_user.id, id, "UNMUTE")


@router.post("/topics/{id}/adjust", summary="Adjust topic feedback")
async def adjust_topic(
    id: uuid.UUID = Path(..., description="Topic UUID"),
    action: str = Body(..., embed=True, description="MORE | LESS | NOT_INTERESTED | KEEP"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Adjust preference for an inferred topic."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_topic(current_user.id, id, action)


@router.post("/entities/{id}/follow", summary="Follow entity")
async def follow_entity(
    id: uuid.UUID = Path(..., description="Entity UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Follow a specific entity."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_entity(current_user.id, id, "FOLLOW")


@router.post("/entities/{id}/mute", summary="Mute entity")
async def mute_entity(
    id: uuid.UUID = Path(..., description="Entity UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mute a specific entity."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_entity(current_user.id, id, "MUTE")


@router.post("/entities/{id}/less", summary="See less of entity")
async def see_less_entity(
    id: uuid.UUID = Path(..., description="Entity UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Decrease preference for an entity."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_entity(current_user.id, id, "LESS")


@router.post("/sources/{id}/prefer", summary="Prefer news source")
async def prefer_source(
    id: uuid.UUID = Path(..., description="News Source UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Prefer stories from this news source."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_source(current_user.id, id, "PREFER")


@router.post("/sources/{id}/mute", summary="Mute news source")
async def mute_source(
    id: uuid.UUID = Path(..., description="News Source UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mute stories from this news source."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_source(current_user.id, id, "MUTE")


@router.post("/sources/{id}/reduce", summary="Reduce news source")
async def reduce_source(
    id: uuid.UUID = Path(..., description="News Source UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reduce frequency of stories from this source."""
    service = PersonalizationControlCenterService(db)
    return await service.manage_source(current_user.id, id, "REDUCE")


@router.get("/explanation/{article_id}", response_model=WhyThisStoryResponse, summary="Why am I seeing this?")
async def get_story_explanation(
    article_id: uuid.UUID = Path(..., description="Article UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Provide transparent, human-readable reasons why this story was recommended."""
    service = PersonalizationControlCenterService(db)
    try:
        return await service.explain_why_story(current_user.id, article_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/pause", summary="Pause personalization learning")
async def pause_learning(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pause automatic behavior learning without erasing existing profile."""
    service = PersonalizationControlCenterService(db)
    return await service.pause_learning(current_user.id)


@router.post("/resume", summary="Resume personalization learning")
async def resume_learning(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume automatic behavior learning."""
    service = PersonalizationControlCenterService(db)
    return await service.resume_learning(current_user.id)


@router.post("/reset", summary="Reset personalization profile")
async def reset_personalization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset inferred behavioral preferences (preserves explicit interests & saved articles)."""
    service = PersonalizationControlCenterService(db)
    return await service.reset_personalization(current_user.id)


@router.post("/rebuild", summary="Rebuild profile from evidence logs")
async def rebuild_personalization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recomputes derived preferences from historical evidence logs."""
    service = PersonalizationControlCenterService(db)
    return await service.rebuild_personalization(current_user.id)


@router.post("/clear-temporary", summary="Clear short-term/trending interests")
async def clear_temporary_interests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clears temporary session boosts and active story affinity signals."""
    service = PersonalizationControlCenterService(db)
    return await service.clear_temporary_interests(current_user.id)
