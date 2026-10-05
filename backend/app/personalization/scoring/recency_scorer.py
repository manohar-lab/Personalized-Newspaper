"""recency_scorer.py — Recency Decay Scorer.

Computes time-decay relevance using half-life exponential decay:
    score = 0.5 ** (age_hours / half_life_hours)
"""
import math
from datetime import datetime, timezone
from typing import Optional
from app.core.config import settings


class RecencyScorer:
    """Calculates recency decay score for articles based on publication timestamp."""

    @staticmethod
    def score_recency(
        published_at: Optional[datetime],
        created_at: Optional[datetime] = None,
        now: Optional[datetime] = None,
        half_life_hours: Optional[float] = None,
    ) -> float:
        """Calculate recency score in [0.0, 1.0].
        
        Args:
            published_at: Article publication timestamp
            created_at: Fallback creation timestamp
            now: Reference time (defaults to current UTC time)
            half_life_hours: Half-life in hours for decay (defaults to settings.PERSONALIZATION_RECENCY_HALF_LIFE_HOURS)
        """
        ref_time = now or datetime.now(timezone.utc)
        target_dt = published_at or created_at or ref_time

        # Ensure tz-aware comparison
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        half_life = (
            half_life_hours
            if half_life_hours is not None and half_life_hours > 0
            else settings.PERSONALIZATION_RECENCY_HALF_LIFE_HOURS
        )

        age_seconds = (ref_time - target_dt).total_seconds()
        age_hours = age_seconds / 3600.0

        # Articles with future publication timestamps receive maximum recency score 1.0
        if age_hours <= 0.0:
            return 1.0

        # Exponential decay: score = 0.5 ** (age_hours / half_life)
        # = exp(-ln(2) * age_hours / half_life)
        decay = math.exp(-0.69314718056 * (age_hours / half_life))

        if math.isnan(decay) or math.isinf(decay):
            return 0.5

        clamped = max(0.0, min(1.0, decay))
        return round(clamped, 4)
