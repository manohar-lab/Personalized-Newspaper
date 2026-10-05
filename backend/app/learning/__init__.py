"""learning module — Phase 8 Automatic User Interest Learning."""
from app.learning.models import (
    UserBehaviorEvent,
    ReadingSession,
    UserEntityInterest,
    UserKeywordInterest,
)
from app.learning.schemas import (
    BehaviorEventCreate,
    BehaviorEventResponse,
    ReadingStartRequest,
    ReadingStartResponse,
    ReadingEndRequest,
    ReadingEndResponse,
    LearnedInterestItem,
    UserLearningProfileResponse,
)
from app.learning.agent import InterestLearningAgent

__all__ = [
    "UserBehaviorEvent",
    "ReadingSession",
    "UserEntityInterest",
    "UserKeywordInterest",
    "BehaviorEventCreate",
    "BehaviorEventResponse",
    "ReadingStartRequest",
    "ReadingStartResponse",
    "ReadingEndRequest",
    "ReadingEndResponse",
    "LearnedInterestItem",
    "UserLearningProfileResponse",
    "InterestLearningAgent",
]
