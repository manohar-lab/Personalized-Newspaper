from app.models.base import Base
from app.models.user import User, UserProfile
from app.models.topic import Topic
from app.models.interest import UserInterest

__all__ = ["Base", "User", "UserProfile", "Topic", "UserInterest"]
