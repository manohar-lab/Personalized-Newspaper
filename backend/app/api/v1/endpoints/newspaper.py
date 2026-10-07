"""newspaper.py — Phase 17 Newspaper Edition API Endpoints."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.newspaper_service import NewspaperService
from app.newspaper.schemas import NewspaperEditionResponse, GenerateEditionRequest
from app.editorial.schemas import EditionStatusResponse, EditionVersionSummary

router = APIRouter()


@router.get("/today", response_model=NewspaperEditionResponse, summary="Get today's personalized newspaper edition")
@router.get("", response_model=NewspaperEditionResponse, include_in_schema=False)
async def get_today_newspaper(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get today's personalized newspaper edition.
    If today's edition has already been generated, returns the latest stored snapshot.
    If not yet generated, generates and persists it automatically using the user's timezone.
    """
    service = NewspaperService(db)
    return await service.get_personalized_newspaper(user=current_user)


@router.get("/{edition_date}/versions", response_model=List[EditionVersionSummary], summary="List all edition versions for date")
async def get_newspaper_edition_versions(
    edition_date: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all edition versions generated for a specific date (YYYY-MM-DD)."""
    service = NewspaperService(db)
    return await service.get_edition_versions(current_user.id, edition_date)


@router.get("/{edition_date}/status", response_model=EditionStatusResponse, summary="Check status and staleness of edition")
async def get_newspaper_edition_status(
    edition_date: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check whether a specific edition is ready or stale."""
    service = NewspaperService(db)
    return await service.get_edition_status(current_user.id, edition_date)


@router.get("/editions/{edition_date}", response_model=NewspaperEditionResponse, summary="Get historical daily edition snapshot")
async def get_newspaper_edition_by_date_legacy(
    edition_date: str,
    version: Optional[int] = Query(default=None, description="Optional specific version"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific historical daily edition snapshot (YYYY-MM-DD)."""
    service = NewspaperService(db)
    edition = await service.get_edition_by_date(current_user.id, edition_date, version=version)
    if not edition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Newspaper edition for date '{edition_date}' not found.",
        )
    return edition


@router.get("/{edition_date}", response_model=NewspaperEditionResponse, summary="Get edition by date")
async def get_newspaper_edition_by_date(
    edition_date: str,
    version: Optional[int] = Query(default=None, description="Optional specific version"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific daily edition snapshot (YYYY-MM-DD)."""
    service = NewspaperService(db)
    edition = await service.get_edition_by_date(current_user.id, edition_date, version=version)
    if not edition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Newspaper edition for date '{edition_date}' not found.",
        )
    return edition


@router.post("/generate", response_model=NewspaperEditionResponse, summary="Generate a daily newspaper edition")
async def generate_newspaper_edition(
    request: Optional[GenerateEditionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a daily newspaper edition (or a new updated version)."""
    service = NewspaperService(db)
    date_str = request.edition_date if request else None
    force = request.force_refresh if request else False
    if force:
        return await service.regenerate_edition(user=current_user, edition_date=date_str)
    return await service.generate_edition(user=current_user, edition_date=date_str)


@router.post("/regenerate", response_model=NewspaperEditionResponse, summary="Force regenerate edition with new version")
async def regenerate_newspaper_edition(
    request: Optional[GenerateEditionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Force regenerate today's or a specific daily edition, persisting a new version."""
    service = NewspaperService(db)
    date_str = request.edition_date if request else None
    return await service.regenerate_edition(user=current_user, edition_date=date_str)
