"""decay.py — Time-Based Interest Decay Engine.

Applies exponential half-life decay to learned and inferred interests when there is no
recent activity, while explicitly preserving explicit user interests.
"""
import math
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InterestDecayEngine:
    """Calculates continuous exponential decay for dynamic user interests."""

    @staticmethod
    def calculate_decay(
        current_score: float,
        last_positive_at: Optional[datetime],
        interest_type: str = "LEARNED",
        half_life_days: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> float:
        """Apply exponential decay based on days elapsed since the last positive signal.
        
        Formula:
            decayed_score = score * (0.5 ** (days_since_signal / half_life))
        
        Explicit interests never decay.
        """
        if interest_type.upper().strip() == "EXPLICIT":
            return current_score

        if not last_positive_at or current_score <= 0.0:
            return current_score

        eval_now = now or utc_now()
        eval_last = last_positive_at
        if eval_last.tzinfo is None:
            eval_last = eval_last.replace(tzinfo=timezone.utc)
        if eval_now.tzinfo is None:
            eval_now = eval_now.replace(tzinfo=timezone.utc)

        elapsed_seconds = max(0.0, (eval_now - eval_last).total_seconds())
        elapsed_days = elapsed_seconds / 86400.0

        half_life = half_life_days if half_life_days is not None else settings.INTEREST_DECAY_HALF_LIFE_DAYS
        if half_life <= 0:
            return current_score

        # Exponential decay factor: 0.5 ^ (days / half_life)
        decay_factor = math.pow(0.5, elapsed_days / half_life)
        decayed_score = current_score * decay_factor

        # Clamp between 0.0 and 1.0
        return round(max(0.0, min(1.0, decayed_score)), 4)
