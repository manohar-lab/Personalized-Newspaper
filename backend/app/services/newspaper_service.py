"""newspaper_service.py — Newspaper Service delegating edition generation to EditorialNewsroom."""
import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.editorial.editor import EditorialNewsroom
from app.editorial.schemas import (
    EditionStatusResponse,
    EditionVersionSummary,
    EditorialDebugResponse,
)
from app.newspaper.schemas import NewspaperEditionResponse


class NewspaperService:
    """Entry point for newspaper edition generation, delegating to the Phase 17 EditorialNewsroom."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.newsroom = EditorialNewsroom(session)

    async def get_personalized_newspaper(self, user: User) -> NewspaperEditionResponse:
        """Fetch today's personalized newspaper edition for user."""
        return await self.newsroom.get_today_edition(user)

    async def get_edition_by_date(
        self, user_id: uuid.UUID, edition_date: str, version: Optional[int] = None
    ) -> Optional[NewspaperEditionResponse]:
        """Fetch a specific edition date snapshot (and optional version)."""
        return await self.newsroom.get_edition_by_date(user_id, edition_date, version=version)

    async def get_edition_versions(
        self, user_id: uuid.UUID, edition_date: str
    ) -> List[EditionVersionSummary]:
        """Fetch all versions for a given date."""
        return await self.newsroom.get_edition_versions(user_id, edition_date)

    async def get_edition_status(
        self, user_id: uuid.UUID, edition_date: str
    ) -> EditionStatusResponse:
        """Check status and staleness of an edition."""
        return await self.newsroom.get_edition_status(user_id, edition_date)

    async def generate_daily_edition(
        self,
        user_id: Optional[uuid.UUID] = None,
        user: Optional[User] = None,
        edition_date: Optional[str] = None,
        target_date: Optional[str] = None,
        force_refresh: bool = False,
        force_regenerate: bool = False,
    ) -> NewspaperEditionResponse:
        """Generate or refresh daily edition for user."""
        resolved_uid = user.id if (user is not None and hasattr(user, "id")) else user_id
        target_d = edition_date or target_date
        return await self.newsroom.generate_edition(
            user_id=resolved_uid,
            edition_date=target_d,
            force_refresh=force_refresh or force_regenerate,
        )

    async def generate_edition(
        self, user: User, edition_date: Optional[str] = None
    ) -> NewspaperEditionResponse:
        """Generate a new daily edition."""
        return await self.newsroom.generate_edition(
            user_id=user.id, edition_date=edition_date, force_refresh=False
        )

    async def regenerate_edition(
        self, user: User, edition_date: Optional[str] = None
    ) -> NewspaperEditionResponse:
        """Regenerate today's or a specific edition, creating a new version."""
        return await self.newsroom.generate_edition(
            user_id=user.id, edition_date=edition_date, force_refresh=True
        )

    async def get_editorial_debug(
        self, user_id: uuid.UUID, edition_date: str
    ) -> EditorialDebugResponse:
        """Fetch protected editorial debug decision logs."""
        return await self.newsroom.get_editorial_debug(user_id, edition_date)
