"""scoring.py — Interest Score & Confidence Calculation and State Classification.

Computes updated scores, confidence saturation, and classifies dynamic interest states
(STRONG, EMERGING, STABLE, DECLINING, DORMANT).
"""
import enum
import math
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.core.config import settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InterestState(str, enum.Enum):
    STRONG = "STRONG"
    EMERGING = "EMERGING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"
    DORMANT = "DORMANT"


class InterestScoringEngine:
    """Calculates updated scores, confidence, and state classifications."""

    @staticmethod
    def calculate_confidence(evidence_count: int, explicit: bool = False) -> float:
        """Calculate confidence based on evidence count using saturation curve.
        
        Explicit interests start at high confidence (0.95+).
        Learned interests scale gracefully from 0.15 up to 0.95.
        """
        if explicit:
            return 1.0

        count = max(0, evidence_count)
        # Asymptotic saturation curve: 1 - exp(-0.15 * count)
        conf = 1.0 - math.exp(-0.15 * count)
        clamped = max(settings.MIN_INTEREST_CONFIDENCE, min(settings.MAX_INTEREST_CONFIDENCE, conf))
        return round(clamped, 4)

    @staticmethod
    def update_score(
        current_score: float,
        signal_delta: float,
        learning_rate: Optional[float] = None,
        is_negative_pref: bool = False,
    ) -> float:
        """Update score incrementally given a combined signal delta."""
        lr = learning_rate if learning_rate is not None else settings.INTEREST_LEARNING_RATE
        scaled_delta = signal_delta * lr

        if is_negative_pref:
            # Negative preference: negative signal increases suppression (0.0), positive softens it
            new_score = max(0.0, min(1.0, current_score + scaled_delta))
        else:
            new_score = max(0.0, min(1.0, current_score + scaled_delta))

        return round(new_score, 4)

    @staticmethod
    def classify_state(
        score: float,
        confidence: float,
        evidence_count: int,
        positive_count: int,
        negative_count: int,
        last_positive_at: Optional[datetime],
        interest_type: str = "LEARNED",
        now: Optional[datetime] = None,
    ) -> InterestState:
        """Classify dynamic interest state based on score, confidence, velocity, and recency."""
        eval_now = now or utc_now()
        days_since_active = 0.0
        if last_positive_at:
            eval_last = last_positive_at
            if eval_last.tzinfo is None:
                eval_last = eval_last.replace(tzinfo=timezone.utc)
            if eval_now.tzinfo is None:
                eval_now = eval_now.replace(tzinfo=timezone.utc)
            days_since_active = max(0.0, (eval_now - eval_last).total_seconds() / 86400.0)

        # 1. Dormant: long inactivity or very low score
        if days_since_active >= settings.INTEREST_DORMANT_DAYS or (score < 0.25 and evidence_count > 2):
            return InterestState.DORMANT

        # 2. Strong: high score and high confidence
        if score >= settings.INTEREST_STRONG_THRESHOLD and (confidence >= 0.50 or interest_type == "EXPLICIT"):
            return InterestState.STRONG

        # 3. Emerging: strong recent positive activity with moderate evidence (recent discovery)
        if (
            interest_type in ("LEARNED", "INFERRED")
            and positive_count >= 2
            and positive_count >= (negative_count * 2)
            and days_since_active <= 7.0
            and confidence < 0.65
        ):
            return InterestState.EMERGING

        # 4. Declining: negative count high or score decaying from inactivity
        if (
            negative_count > positive_count
            or (days_since_active > 20.0 and score < 0.50)
        ):
            return InterestState.DECLINING

        # 5. Stable: established interest
        if score >= settings.INTEREST_STABLE_THRESHOLD:
            return InterestState.STABLE

        return InterestState.DORMANT
