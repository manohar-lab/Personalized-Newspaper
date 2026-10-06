"""signals.py — Centralized Behavioral Signal Resolution and Event Logging.

Defines signal types, dynamic weight resolution from settings, and learning event creation
with deduplication and cursor management.
"""
import enum
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.interest_profile import InterestLearningEvent

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SignalType(str, enum.Enum):
    EXPLICIT_INTEREST = "EXPLICIT_INTEREST"
    ARTICLE_OPEN = "ARTICLE_OPEN"
    LIKE = "LIKE"
    SAVE = "SAVE"
    NOT_INTERESTED = "NOT_INTERESTED"
    DEEP_READ = "DEEP_READ"
    REPEAT_READ = "REPEAT_READ"
    NORMAL_READ = "NORMAL_READ"
    SEARCH = "SEARCH"
    SHORT_READ = "SHORT_READ"
    BOUNCE = "BOUNCE"
    ARTICLE_IMPRESSION = "ARTICLE_IMPRESSION"


class SignalManager:
    """Manages signal weights, prioritization, and persistent learning event logging."""

    @staticmethod
    def get_signal_weight(signal_type: str, raw_multiplier: float = 1.0) -> float:
        """Resolve configurable weight for a given behavioral signal."""
        norm_type = signal_type.upper().strip()

        weights_map = {
            SignalType.EXPLICIT_INTEREST.value: settings.SIGNAL_WEIGHT_EXPLICIT_INTEREST,
            SignalType.ARTICLE_OPEN.value: settings.WEIGHT_ARTICLE_OPEN,
            SignalType.LIKE.value: settings.SIGNAL_WEIGHT_LIKE,
            SignalType.SAVE.value: settings.SIGNAL_WEIGHT_SAVE,
            SignalType.NOT_INTERESTED.value: settings.SIGNAL_WEIGHT_NOT_INTERESTED,
            SignalType.DEEP_READ.value: settings.SIGNAL_WEIGHT_DEEP_READ,
            SignalType.REPEAT_READ.value: settings.SIGNAL_WEIGHT_REPEAT_READ,
            SignalType.NORMAL_READ.value: settings.SIGNAL_WEIGHT_NORMAL_READ,
            SignalType.SEARCH.value: settings.SIGNAL_WEIGHT_SEARCH,
            SignalType.SHORT_READ.value: settings.SIGNAL_WEIGHT_SHORT_READ,
            SignalType.BOUNCE.value: settings.SIGNAL_WEIGHT_BOUNCE,
            SignalType.ARTICLE_IMPRESSION.value: settings.SIGNAL_WEIGHT_ARTICLE_IMPRESSION,
        }

        base_weight = weights_map.get(norm_type, 0.0)
        # Apply scaling multiplier if relevant
        if raw_multiplier > 0 and norm_type in (
            SignalType.NORMAL_READ.value,
            SignalType.DEEP_READ.value,
            SignalType.SEARCH.value,
        ):
            clamped_mult = max(0.5, min(2.0, raw_multiplier))
            return base_weight * clamped_mult

        return base_weight

    @staticmethod
    async def log_event(
        session: AsyncSession,
        user_id: uuid.UUID,
        signal_type: str,
        article_id: Optional[uuid.UUID] = None,
        topic_id: Optional[uuid.UUID] = None,
        entity_id: Optional[uuid.UUID] = None,
        source: Optional[str] = "READER",
        metadata: Optional[Dict[str, Any]] = None,
        multiplier: float = 1.0,
    ) -> InterestLearningEvent:
        """Record an unprocessed learning event with cursor state."""
        weight = SignalManager.get_signal_weight(signal_type, multiplier)
        now = utc_now()

        event = InterestLearningEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            article_id=article_id,
            topic_id=topic_id,
            entity_id=entity_id,
            signal_type=signal_type.upper().strip(),
            signal_strength=weight,
            source=source,
            processed=False,
            event_metadata=metadata,
            created_at=now,
        )
        session.add(event)
        return event
