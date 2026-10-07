"""preferences.py — Phase 22 User Newspaper Preferences & Edition Settings Schemas."""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserNewspaperPreferencesBase(BaseModel):
    morning_enabled: bool = True
    morning_time: str = Field(default="07:00", pattern=r"^\d{2}:\d{2}$")
    midday_enabled: bool = True
    midday_time: str = Field(default="13:00", pattern=r"^\d{2}:\d{2}$")
    evening_enabled: bool = True
    evening_time: str = Field(default="19:00", pattern=r"^\d{2}:\d{2}$")
    timezone: str = "UTC"
    edition_frequency: str = "DAILY"  # DAILY | TWICE_DAILY | THRICE_DAILY | BREAKING_ONLY
    breaking_news_enabled: bool = True


class UserNewspaperPreferencesUpdate(BaseModel):
    morning_enabled: Optional[bool] = None
    morning_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    midday_enabled: Optional[bool] = None
    midday_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    evening_enabled: Optional[bool] = None
    evening_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    timezone: Optional[str] = None
    edition_frequency: Optional[str] = None
    breaking_news_enabled: Optional[bool] = None


class UserNewspaperPreferencesResponse(UserNewspaperPreferencesBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
