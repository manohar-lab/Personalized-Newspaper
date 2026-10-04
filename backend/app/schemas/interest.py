import uuid
from datetime import datetime
from typing import List, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict

PreferenceType = Literal["POSITIVE", "NEGATIVE"]
InterestSource = Literal["ONBOARDING", "USER_ACTION", "AGENT", "SYSTEM"]

class UserInterestItem(BaseModel):
    topic_slug: str
    interest_score: float = Field(..., ge=0.0, le=1.0, description="Interest score between 0.0 and 1.0")
    preference_type: PreferenceType

    @field_validator("preference_type")
    @classmethod
    def validate_preference_type(cls, v: str) -> str:
        upper_v = v.upper()
        if upper_v not in ("POSITIVE", "NEGATIVE"):
            raise ValueError("preference_type must be POSITIVE or NEGATIVE")
        return upper_v

class UserInterestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_slug: str
    topic_name: str
    interest_score: float
    preference_type: str
    source: str
    created_at: datetime
    updated_at: datetime

class UpdateInterestsRequest(BaseModel):
    interests: List[UserInterestItem]

class OnboardingInterestsRequest(BaseModel):
    positive_topics: List[str] = Field(default_factory=list)
    negative_topics: List[str] = Field(default_factory=list)
