import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, UUID, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.article import Article

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class ActionType(str, Enum):
    SAVE = "SAVE"
    LIKE = "LIKE"
    NOT_INTERESTED = "NOT_INTERESTED"

class UserArticleAction(Base):
    __tablename__ = "user_article_actions"

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
    action: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # SAVE | LIKE | NOT_INTERESTED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="actions")
    article: Mapped["Article"] = relationship("Article", back_populates="actions")

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", "action", name="uq_user_article_action"),
    )
