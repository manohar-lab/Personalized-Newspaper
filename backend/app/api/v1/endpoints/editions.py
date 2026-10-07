"""editions.py — Phase 22 Standardized Edition Retrieval & Status Endpoints."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Path
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.article import Article
from app.newspaper.models import NewspaperEdition, NewspaperStory
from app.newspaper.schemas import NewspaperEditionResponse, NewspaperStoryResponse
from app.newspaper.generator import NewspaperGenerationService
from app.services.newspaper_service import NewspaperService

router = APIRouter()


@router.get("/latest", response_model=NewspaperEditionResponse, summary="Get latest published edition snapshot")
async def get_latest_edition(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the latest immutable edition snapshot for the authenticated user."""
    stmt = (
        select(NewspaperEdition)
        .where(
            NewspaperEdition.user_id == current_user.id,
            NewspaperEdition.status == "READY",
        )
        .order_by(
            desc(NewspaperEdition.edition_date),
            desc(NewspaperEdition.version),
            desc(NewspaperEdition.generated_at),
        )
        .limit(1)
    )
    res = await db.execute(stmt)
    latest = res.scalar_one_or_none()

    service = NewspaperService(db)
    if latest:
        return await service.get_edition_by_date(
            current_user.id, latest.edition_date, version=latest.version
        )

    # If no stored edition exists yet, generate on the fly
    return await service.get_personalized_newspaper(user=current_user)


@router.get("", response_model=List[dict], summary="List past editions for user")
async def list_editions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated history of user's past newspaper editions."""
    offset = (page - 1) * limit
    stmt = (
        select(NewspaperEdition)
        .where(NewspaperEdition.user_id == current_user.id)
        .order_by(
            desc(NewspaperEdition.edition_date),
            desc(NewspaperEdition.version),
        )
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    editions = list(res.scalars().all())

    return [
        {
            "id": str(e.id),
            "edition_date": e.edition_date,
            "edition_type": getattr(e, "edition_type", "MORNING"),
            "version": e.version,
            "title": e.title,
            "subtitle": e.subtitle,
            "status": e.status,
            "generated_at": e.generated_at.isoformat() if e.generated_at else None,
            "published_at": e.published_at.isoformat() if getattr(e, "published_at", None) else None,
        }
        for e in editions
    ]


@router.get("/{id}", response_model=NewspaperEditionResponse, summary="Get edition by ID")
async def get_edition_by_id(
    id: uuid.UUID = Path(..., description="Newspaper Edition UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full edition details by UUID (enforcing user isolation)."""
    stmt = (
        select(NewspaperEdition)
        .where(
            NewspaperEdition.id == id,
            NewspaperEdition.user_id == current_user.id,
        )
    )
    res = await db.execute(stmt)
    edition = res.scalar_one_or_none()
    if not edition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Newspaper edition not found",
        )

    service = NewspaperService(db)
    return await service.get_edition_by_date(
        current_user.id, edition.edition_date, version=edition.version
    )


@router.get("/{id}/stories", response_model=List[dict], summary="Get stories in edition")
async def get_edition_stories(
    id: uuid.UUID = Path(..., description="Newspaper Edition UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all selected stories belonging to this edition snapshot."""
    stmt = (
        select(NewspaperStory)
        .join(NewspaperEdition, NewspaperStory.edition_id == NewspaperEdition.id)
        .where(
            NewspaperStory.edition_id == id,
            NewspaperEdition.user_id == current_user.id,
        )
        .options(
            selectinload(NewspaperStory.article).selectinload(Article.source),
            selectinload(NewspaperStory.article).selectinload(Article.topics),
        )
        .order_by(NewspaperStory.position.asc())
    )
    res = await db.execute(stmt)
    stories = list(res.scalars().all())

    return [
        {
            "id": str(s.id),
            "article_id": str(s.article_id) if s.article_id else None,
            "title": s.article.title if s.article else "",
            "layout_type": s.layout_type,
            "section": s.section,
            "position": s.position,
            "editorial_reason": s.personalization_reason or s.reason or "",
            "score": s.editorial_score,
        }
        for s in stories
    ]


@router.get("/{id}/status", summary="Get edition generation status")
async def get_edition_status_by_id(
    id: uuid.UUID = Path(..., description="Newspaper Edition UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check the status and freshness of an edition."""
    stmt = (
        select(NewspaperEdition)
        .where(
            NewspaperEdition.id == id,
            NewspaperEdition.user_id == current_user.id,
        )
    )
    res = await db.execute(stmt)
    edition = res.scalar_one_or_none()
    if not edition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Newspaper edition not found",
        )

    return {
        "id": str(edition.id),
        "status": edition.status,
        "edition_type": getattr(edition, "edition_type", "MORNING"),
        "version": edition.version,
        "generated_at": edition.generated_at.isoformat() if edition.generated_at else None,
        "published_at": edition.published_at.isoformat() if getattr(edition, "published_at", None) else None,
        "is_ready": edition.status == "READY",
    }
