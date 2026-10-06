"""freshness.py — Publication freshness decay & category-aware half-life models."""
import math
from datetime import datetime, timezone
from typing import Optional


class FreshnessCalculator:
    """Calculates freshness decay scores and source publication cadence."""

    DEFAULT_HALF_LIFE_HOURS: float = 48.0

    CATEGORY_HALF_LIVES = {
        "WORLD": 24.0,
        "POLITICS": 24.0,
        "BREAKING": 12.0,
        "TECHNOLOGY": 48.0,
        "BUSINESS": 48.0,
        "FINANCE": 36.0,
        "SCIENCE": 72.0,
        "HEALTH": 72.0,
        "RESEARCH": 168.0,      # 7 days
        "TUTORIAL": 336.0,      # 14 days (Evergreen)
        "ANALYSIS": 96.0,
        "OPINION": 72.0,
    }

    @classmethod
    def get_category_half_life(cls, category: Optional[str], article_type: Optional[str] = None) -> float:
        if article_type and article_type.upper() in cls.CATEGORY_HALF_LIVES:
            return cls.CATEGORY_HALF_LIVES[article_type.upper()]
        if category and category.upper() in cls.CATEGORY_HALF_LIVES:
            return cls.CATEGORY_HALF_LIVES[category.upper()]
        return cls.DEFAULT_HALF_LIFE_HOURS

    @classmethod
    def calculate_article_freshness(
        cls,
        published_at: Optional[datetime],
        category: Optional[str] = None,
        article_type: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> float:
        """
        Calculates exponential time-decay freshness score [0.0, 1.0].
        Score = exp(-age_hours / half_life)
        """
        if not published_at:
            return 0.50

        if now is None:
            now = datetime.now(timezone.utc)

        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        age_seconds = max(0.0, (now - published_at).total_seconds())
        age_hours = age_seconds / 3600.0

        half_life = cls.get_category_half_life(category, article_type)
        freshness = math.exp(-age_hours / half_life)
        return round(min(1.0, max(0.05, freshness)), 4)

    @staticmethod
    def calculate_source_freshness(
        last_published_at: Optional[datetime],
        article_count_last_7_days: int = 0,
        now: Optional[datetime] = None,
    ) -> float:
        """Evaluates overall source cadence and freshness."""
        if not last_published_at:
            return 0.30

        if now is None:
            now = datetime.now(timezone.utc)

        if last_published_at.tzinfo is None:
            last_published_at = last_published_at.replace(tzinfo=timezone.utc)

        age_hours = max(0.0, (now - last_published_at).total_seconds()) / 3600.0

        # Recency component: actively publishing within 24h -> high score
        if age_hours <= 12.0:
            recency_component = 1.0
        elif age_hours <= 36.0:
            recency_component = 0.85
        elif age_hours <= 72.0:
            recency_component = 0.65
        elif age_hours <= 168.0:
            recency_component = 0.40
        else:
            recency_component = 0.15

        # Volume component: 1-20 articles/week scale
        volume_component = min(1.0, article_count_last_7_days / 15.0)

        score = (recency_component * 0.70) + (volume_component * 0.30)
        return round(score, 4)
