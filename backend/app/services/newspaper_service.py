"""newspaper_service.py — Newspaper Service delegating edition generation to NewspaperGenerationService."""
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.newspaper.generator import NewspaperGenerationService
from app.newspaper.schemas import NewspaperEditionResponse


class NewspaperService:
    """Entry point for newspaper generation, delegating edition building to NewspaperGenerationService."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.generation_service = NewspaperGenerationService(session)

    async def get_personalized_newspaper(self, user: User) -> NewspaperEditionResponse:
        """Fetch today's personalized newspaper edition for user."""
        return await self.generation_service.get_or_generate_today_edition(user)

    async def get_edition_by_date(
        self, user_id: uuid.UUID, edition_date: str
    ) -> Optional[NewspaperEditionResponse]:
        """Fetch a specific edition date snapshot."""
        return await self.generation_service.get_edition_by_date(user_id, edition_date)

    async def generate_edition(
        self, user: User, edition_date: Optional[str] = None
    ) -> NewspaperEditionResponse:
        """Generate a new daily edition."""
        return await self.generation_service.generate_daily_edition(
            user=user, edition_date=edition_date, force_regenerate=False
        )

    async def regenerate_edition(
        self, user: User, edition_date: Optional[str] = None
    ) -> NewspaperEditionResponse:
        """Regenerate today's or a specific edition."""
        return await self.generation_service.generate_daily_edition(
            user=user, edition_date=edition_date, force_regenerate=True
        )
