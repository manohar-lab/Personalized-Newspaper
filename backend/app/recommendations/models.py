"""models.py — Phase 14 Recommendation History & Impressions Model."""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, UUID, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.article import Article


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRecommendation(Base):
    """Tracks recommended articles per user, scoring context, impressions, clicks, and cooldowns."""

    __tablename__ = "user_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context: Mapped[str] = mapped_column(
        String(30), default="DISCOVER", nullable=False, index=True
    )
    recommendation_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reason_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_text: Mapped[str] = mapped_column(String(255), nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    is_shown: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shown_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_clicked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    recommended_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", backref="recommendations")
    article: Mapped["Article"] = relationship("Article", backref="recommendations")

    __table_args__ = (
        Index("ix_user_rec_user_context", "user_id", "context"),
        Index("ix_user_rec_user_article", "user_id", "article_id"),
        Index("ix_user_rec_user_date", "user_id", "recommended_at"),
    )
