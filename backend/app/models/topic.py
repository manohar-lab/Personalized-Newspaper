import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import String, Text, DateTime, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.interest import UserInterest

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    parent_topic: Mapped[Optional["Topic"]] = relationship(
        "Topic", remote_side=[id], backref="subtopics"
    )
    user_interests: Mapped[List["UserInterest"]] = relationship(
        "UserInterest", back_populates="topic", cascade="all, delete-orphan"
    )
