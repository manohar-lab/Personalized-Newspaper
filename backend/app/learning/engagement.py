"""engagement.py — Deterministic Reading Engagement Intelligence & Scoring.

Provides mathematically grounded scoring, multi-tier engagement classification,
and signal derivation for automatic user interest learning.
"""
from typing import Dict, Any, Optional
from app.core.config import settings


class EngagementIntelligence:
    """Calculates engagement score and classifies reading session & history levels."""

    @staticmethod
    def calculate_engagement_score(
        duration_seconds: float,
        expected_reading_seconds: float = 180.0,
        max_scroll_percentage: float = 0.0,
        completion_percentage: float = 0.0,
        open_count: int = 1,
        is_completed: bool = False,
        has_liked: bool = False,
        has_saved: bool = False,
    ) -> float:
        """Compute deterministic normalized engagement score in [0.0, 1.0]."""
        exp_sec = max(30.0, float(expected_reading_seconds))
        dur_sec = max(0.0, float(duration_seconds))
        max_scroll = max(0.0, min(100.0, float(max_scroll_percentage)))
        comp_pct = max(0.0, min(100.0, float(completion_percentage)))

        # 1. Duration component
        duration_score = min(1.0, dur_sec / exp_sec)

        # 2. Scroll depth component
        scroll_score = max_scroll / 100.0

        # 3. Completion component
        if is_completed or comp_pct >= settings.ARTICLE_COMPLETION_THRESHOLD:
            completion_score = 1.0
        else:
            completion_score = comp_pct / 100.0

        # 4. Return visits component
        return_score = min(1.0, (open_count - 1) * 0.5) if open_count > 1 else 0.0

        # Base weighted score
        score = (
            settings.ENGAGEMENT_DURATION_WEIGHT * duration_score
            + settings.ENGAGEMENT_SCROLL_WEIGHT * scroll_score
            + settings.ENGAGEMENT_COMPLETION_WEIGHT * completion_score
            + settings.ENGAGEMENT_RETURN_WEIGHT * return_score
        )

        # Explicit bonus
        if has_liked:
            score += 0.05
        if has_saved:
            score += 0.05

        return round(max(0.0, min(1.0, score)), 4)

    @staticmethod
    def classify_engagement_level(
        duration_seconds: float,
        expected_reading_seconds: float = 180.0,
        max_scroll_percentage: float = 0.0,
        completion_percentage: float = 0.0,
        open_count: int = 1,
        is_completed: bool = False,
    ) -> str:
        """Classify engagement into BOUNCED, LOW, MEDIUM, HIGH, or DEEP."""
        dur_sec = max(0.0, float(duration_seconds))
        exp_sec = max(30.0, float(expected_reading_seconds))
        max_scroll = max(0.0, min(100.0, float(max_scroll_percentage)))
        comp_pct = max(0.0, min(100.0, float(completion_percentage)))

        # Immediate bounce
        if dur_sec < settings.MINIMUM_MEANINGFUL_READ_SECONDS:
            return "BOUNCED"

        is_high_completion = is_completed or comp_pct >= settings.ARTICLE_COMPLETION_THRESHOLD or max_scroll >= settings.ARTICLE_COMPLETION_THRESHOLD

        # DEEP: High completion + substantial reading duration + (return visit OR very thorough read)
        if is_high_completion and (
            (dur_sec >= exp_sec * 0.6 and open_count >= 2)
            or (dur_sec >= exp_sec * 0.85)
            or (dur_sec >= settings.DEEP_READ_DURATION_SECONDS and max_scroll >= 85.0)
        ):
            return "DEEP"

        # HIGH: High completion with meaningful duration
        if is_high_completion and dur_sec >= min(50.0, exp_sec * 0.35):
            return "HIGH"

        # MEDIUM: Meaningful reading time or solid scroll progress
        if dur_sec >= settings.LOW_ENGAGEMENT_THRESHOLD_SECONDS or max_scroll >= 50.0 or comp_pct >= 40.0:
            return "MEDIUM"

        # LOW: Elapsed minimum read time but incomplete
        if dur_sec >= settings.MINIMUM_MEANINGFUL_READ_SECONDS:
            return "LOW"

        return "BOUNCED"

    @staticmethod
    def derive_interest_learning_signal(
        engagement_score: float,
        engagement_level: str,
        duration_seconds: float,
        completion_percentage: float,
    ) -> Dict[str, Any]:
        """Derive a single consolidated interest learning signal to prevent duplicate learning events."""
        if engagement_level == "DEEP":
            return {
                "event_type": "ARTICLE_COMPLETE",
                "value": round(1.5 + min(0.5, duration_seconds / 300.0), 2),
                "signal_strength": "DEEP",
                "reading_engagement_signal": min(1.0, engagement_score),
            }
        elif engagement_level == "HIGH":
            return {
                "event_type": "ARTICLE_COMPLETE",
                "value": 1.25,
                "signal_strength": "HIGH",
                "reading_engagement_signal": min(1.0, engagement_score),
            }
        elif engagement_level == "MEDIUM":
            return {
                "event_type": "ARTICLE_READ",
                "value": round(0.75 + min(0.5, completion_percentage / 100.0), 2),
                "signal_strength": "MEDIUM",
                "reading_engagement_signal": min(1.0, engagement_score),
            }
        elif engagement_level == "LOW":
            return {
                "event_type": "ARTICLE_READ",
                "value": 0.40,
                "signal_strength": "LOW",
                "reading_engagement_signal": min(1.0, engagement_score),
            }
        else:  # BOUNCED
            return {
                "event_type": "ARTICLE_SKIP",
                "value": 0.20,
                "signal_strength": "BOUNCED",
                "reading_engagement_signal": 0.05,
            }
