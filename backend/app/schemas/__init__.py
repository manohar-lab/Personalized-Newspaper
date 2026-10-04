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
from app.schemas.article import (
    TopicSummary,
    ArticleBase,
    ArticleDetailResponse,
    ArticleListResponse,
)
from app.schemas.newspaper import (
    EditionInfo,
    UserSummary,
    NewspaperSection,
    NewspaperResponse,
)
from app.schemas.action import (
    UserActionResponse,
    SavedArticleItem,
    SavedArticlesListResponse,
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
    "TopicSummary",
    "ArticleBase",
    "ArticleDetailResponse",
    "ArticleListResponse",
    "EditionInfo",
    "UserSummary",
    "NewspaperSection",
    "NewspaperResponse",
    "UserActionResponse",
    "SavedArticleItem",
    "SavedArticlesListResponse",
]

