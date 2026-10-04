from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    UserProfileResponse,
    TokenResponse,
)
from app.schemas.topic import TopicResponse
from app.schemas.interest import (
    UserInterestItem,
    UserInterestResponse,
    UpdateInterestsRequest,
    OnboardingInterestsRequest,
)

__all__ = [
    "UserRegister",
    "UserLogin",
    "UserResponse",
    "UserProfileResponse",
    "TokenResponse",
    "TopicResponse",
    "UserInterestItem",
    "UserInterestResponse",
    "UpdateInterestsRequest",
    "OnboardingInterestsRequest",
]
