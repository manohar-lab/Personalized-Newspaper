"""personalization_settings.py — Phase 23 User Personalization & Control Center Settings."""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Any, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    UUID,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserPersonalizationSettings(Base):
    """
    Stores comprehensive user controls over AI personalization strength,
    discovery exploration, topic diversity, learning state, and newspaper section visibility.
    """
    __tablename__ = "user_personalization_settings"

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
    discovery_level: Mapped[str] = mapped_column(
        String(20), default="BALANCED", nullable=False
    )  # FOCUSED | BALANCED | EXPLORATORY
    personalization_strength: Mapped[str] = mapped_column(
        String(20), default="BALANCED", nullable=False
    )  # LOW | BALANCED | HIGH
    diversity_level: Mapped[str] = mapped_column(
        String(20), default="BALANCED", nullable=False
    )  # FOCUSED | BALANCED | DIVERSE
    learning_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    section_preferences: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {
            "TOP_STORIES": "SHOW",
            "TECHNOLOGY": "SHOW",
            "BUSINESS": "SHOW",
            "SCIENCE": "SHOW",
            "WORLD": "SHOW",
            "INDIA": "SHOW",
            "SPORTS": "SHOW",
            "ENTERTAINMENT": "SHOW",
            "DISCOVER": "SHOW",
        },
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="personalization_settings")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_personalization_settings"),
    )
