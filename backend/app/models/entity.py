import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import Table, Column, String, Float, DateTime, ForeignKey, UUID, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.article import Article

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# Junction table for Article <-> Entity (Many-to-Many with confidence)
article_entities = Table(
    "article_entities",
    Base.metadata,
    Column(
        "article_id",
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column(
        "entity_id",
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column(
        "confidence",
        Float,
        default=1.0,
        nullable=False,
    ),
)


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    # PERSON | ORGANIZATION | COMPANY | PRODUCT | TECHNOLOGY | LOCATION | EVENT | OTHER
    entity_type: Mapped[str] = mapped_column(
        String(50), default="OTHER", index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
