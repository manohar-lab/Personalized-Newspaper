"""newspaper_service.py — Newspaper Service delegating curation to PersonalizationService."""
import uuid
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.article import Article
from app.personalization.services.personalization_service import PersonalizationService
from app.schemas.newspaper import NewspaperResponse


class NewspaperService:
    """Entry point for newspaper generation, delegating multi-factor ranking and section curation to PersonalizationService."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.personalization_service = PersonalizationService(session)

    async def get_personalized_newspaper(self, user: User) -> NewspaperResponse:
        """Fetch personalized newspaper edition for user using the multi-factor personalization engine."""
        return await self.personalization_service.build_personalized_newspaper(user)
