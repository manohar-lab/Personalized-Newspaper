from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.newspaper_service import NewspaperService
from app.newspaper.schemas import NewspaperEditionResponse, GenerateEditionRequest

router = APIRouter()


@router.get("/today", response_model=NewspaperEditionResponse)
@router.get("", response_model=NewspaperEditionResponse)
async def get_today_newspaper(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get today's personalized newspaper edition.
    If today's edition has already been generated, returns the stored snapshot.
    If not yet generated, generates and persists it automatically.
    """
    service = NewspaperService(db)
    return await service.get_personalized_newspaper(user=current_user)


@router.get("/editions/{edition_date}", response_model=NewspaperEditionResponse)
async def get_newspaper_edition_by_date(
    edition_date: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific historical daily edition snapshot (YYYY-MM-DD)."""
    service = NewspaperService(db)
    edition = await service.get_edition_by_date(current_user.id, edition_date)
    if not edition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Newspaper edition for date '{edition_date}' not found.",
        )
    return edition


@router.post("/generate", response_model=NewspaperEditionResponse)
async def generate_newspaper_edition(
    request: Optional[GenerateEditionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a daily newspaper edition (if not already generated)."""
    service = NewspaperService(db)
    date_str = request.edition_date if request else None
    return await service.generate_edition(user=current_user, edition_date=date_str)


@router.post("/regenerate", response_model=NewspaperEditionResponse)
async def regenerate_newspaper_edition(
    request: Optional[GenerateEditionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Force regenerate today's or a specific daily edition with updated interests."""
    service = NewspaperService(db)
    date_str = request.edition_date if request else None
    return await service.regenerate_edition(user=current_user, edition_date=date_str)
