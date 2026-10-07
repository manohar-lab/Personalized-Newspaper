"""user_preferences.py — Phase 22 User Newspaper Preferences & Edition Settings Model."""
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UUID,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserNewspaperPreferences(Base):
    __tablename__ = "user_newspaper_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    morning_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    morning_time: Mapped[str] = mapped_column(
        String(8), default="07:00", nullable=False
    )
    midday_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    midday_time: Mapped[str] = mapped_column(
        String(8), default="13:00", nullable=False
    )
    evening_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    evening_time: Mapped[str] = mapped_column(
        String(8), default="19:00", nullable=False
    )
    timezone: Mapped[str] = mapped_column(
        String(64), default="UTC", nullable=False
    )
    edition_frequency: Mapped[str] = mapped_column(
        String(32), default="DAILY", nullable=False
    )  # DAILY | TWICE_DAILY | THRICE_DAILY | BREAKING_ONLY
    breaking_news_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship("User", backref="newspaper_preferences")
