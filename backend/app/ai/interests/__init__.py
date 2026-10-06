"""__init__.py — Phase 13 Dynamic User Interest Intelligence Package."""
from app.ai.interests.signals import SignalManager, SignalType
from app.ai.interests.scoring import InterestScoringEngine, InterestState
from app.ai.interests.decay import InterestDecayEngine
from app.ai.interests.discovery import TopicPropagationEngine
from app.ai.interests.learner import InterestLearningService
from app.ai.interests.schemas import (
    DynamicInterestItem,
    DynamicProfileResponse,
    TopicPreferenceItem,
    EntityAffinityItem,
    UpdateTopicPreferenceRequest,
    ResetLearnedProfileResponse,
    RelevanceExplanationResponse,
)

__all__ = [
    "SignalManager",
    "SignalType",
    "InterestScoringEngine",
    "InterestState",
    "InterestDecayEngine",
    "TopicPropagationEngine",
    "InterestLearningService",
    "DynamicInterestItem",
    "DynamicProfileResponse",
    "TopicPreferenceItem",
    "EntityAffinityItem",
    "UpdateTopicPreferenceRequest",
    "ResetLearnedProfileResponse",
    "RelevanceExplanationResponse",
]
