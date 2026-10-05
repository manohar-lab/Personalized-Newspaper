"""models.py — Phase 8 User Interest Embedding Model.

Persists user interest vector embeddings for fast, deterministic semantic similarity scoring.
"""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import Column, String, DateTime, ForeignKey, UUID, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserInterestEmbedding(Base):
    __tablename__ = "user_interest_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    embedding: Mapped[Any] = mapped_column(JSON, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(20), default="v1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship("User", backref="interest_embeddings")

    __table_args__ = (
        UniqueConstraint("user_id", "embedding_version", name="uq_user_interest_embedding_version"),
    )
