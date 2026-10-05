import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Float, String, DateTime, ForeignKey, UUID, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.topic import Topic

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class UserInterest(Base):
    __tablename__ = "user_interests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interest_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    preference_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="POSITIVE"
    )  # POSITIVE | NEGATIVE
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ONBOARDING"
    )  # ONBOARDING | USER_ACTION | AGENT | SYSTEM | LEARNED | HYBRID
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="interests")
    topic: Mapped["Topic"] = relationship("Topic", back_populates="user_interests")

    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_user_topic"),
        Index("idx_user_topic_pref", "user_id", "topic_id", "preference_type"),
    )
