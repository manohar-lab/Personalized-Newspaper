"""preferences_service.py — Phase 22 User Newspaper Preferences Service."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_preferences import UserNewspaperPreferences
from app.schemas.preferences import UserNewspaperPreferencesUpdate


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PreferencesService:
    """Manages user newspaper edition schedules, timezones, and breaking alerts."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_preferences(self, user_id: uuid.UUID) -> UserNewspaperPreferences:
        """Retrieves or auto-initializes default user newspaper preferences."""
        stmt = select(UserNewspaperPreferences).where(
            UserNewspaperPreferences.user_id == user_id
        )
        res = await self.session.execute(stmt)
        prefs = res.scalar_one_or_none()

        if not prefs:
            now = utc_now()
            prefs = UserNewspaperPreferences(
                id=uuid.uuid4(),
                user_id=user_id,
                morning_enabled=True,
                morning_time="07:00",
                midday_enabled=True,
                midday_time="13:00",
                evening_enabled=True,
                evening_time="19:00",
                timezone="UTC",
                edition_frequency="DAILY",
                breaking_news_enabled=True,
                created_at=now,
                updated_at=now,
            )
            self.session.add(prefs)
            await self.session.commit()
            await self.session.refresh(prefs)

        return prefs

    async def update_user_preferences(
        self,
        user_id: uuid.UUID,
        payload: UserNewspaperPreferencesUpdate,
    ) -> UserNewspaperPreferences:
        """Updates user preferences with validation."""
        prefs = await self.get_user_preferences(user_id)
        now = utc_now()

        update_dict = payload.model_dump(exclude_unset=True)
        for k, v in update_dict.items():
            if v is not None:
                setattr(prefs, k, v)

        prefs.updated_at = now
        await self.session.commit()
        await self.session.refresh(prefs)
        return prefs
