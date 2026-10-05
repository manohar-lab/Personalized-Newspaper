"""schemas.py — Phase 7 AI Structured Output and Validation Schemas.

Defines Pydantic models and Enums for strict validation of LLM outputs.
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class PrimaryCategory(str, Enum):
    TECHNOLOGY = "TECHNOLOGY"
    SCIENCE = "SCIENCE"
    BUSINESS = "BUSINESS"
    FINANCE = "FINANCE"
    WORLD = "WORLD"
    POLITICS = "POLITICS"
    HEALTH = "HEALTH"
    EDUCATION = "EDUCATION"
    SPORTS = "SPORTS"
    ENTERTAINMENT = "ENTERTAINMENT"
    OTHER = "OTHER"


class ArticleType(str, Enum):
    NEWS = "NEWS"
    ANALYSIS = "ANALYSIS"
    OPINION = "OPINION"
    TUTORIAL = "TUTORIAL"
    RESEARCH = "RESEARCH"
    PRODUCT = "PRODUCT"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    INTERVIEW = "INTERVIEW"
    REVIEW = "REVIEW"
    OTHER = "OTHER"


class EntityType(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    COMPANY = "COMPANY"
    PRODUCT = "PRODUCT"
    TECHNOLOGY = "TECHNOLOGY"
    LOCATION = "LOCATION"
    EVENT = "EVENT"
    OTHER = "OTHER"


class TopicExtractionItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return str(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.8


class EntityExtractionItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: EntityType = Field(default=EntityType.OTHER)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return str(v)

    @field_validator("type", mode="before")
    @classmethod
    def coerce_type(cls, v: str) -> EntityType:
        if isinstance(v, str):
            v_upper = v.strip().upper()
            try:
                return EntityType(v_upper)
            except ValueError:
                # Map common aliases
                if "TECH" in v_upper:
                    return EntityType.TECHNOLOGY
                if "ORG" in v_upper:
                    return EntityType.ORGANIZATION
                if "COMP" in v_upper:
                    return EntityType.COMPANY
                if "LOC" in v_upper or "GEO" in v_upper:
                    return EntityType.LOCATION
                return EntityType.OTHER
        return EntityType.OTHER

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.8


class KeywordExtractionItem(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("keyword", mode="before")
    @classmethod
    def clean_keyword(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return str(v).lower()

    @field_validator("weight", mode="before")
    @classmethod
    def clamp_weight(cls, v: float) -> float:
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.8


class ArticleAnalysisOutput(BaseModel):
    primary_category: PrimaryCategory = Field(default=PrimaryCategory.OTHER)
    article_type: ArticleType = Field(default=ArticleType.NEWS)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    language: str = Field(default="en", max_length=10)
    summary: str = Field(..., min_length=10)
    topics: List[TopicExtractionItem] = Field(default_factory=list)
    entities: List[EntityExtractionItem] = Field(default_factory=list)
    keywords: List[KeywordExtractionItem] = Field(default_factory=list)

    @field_validator("primary_category", mode="before")
    @classmethod
    def coerce_category(cls, v: str) -> PrimaryCategory:
        if isinstance(v, str):
            v_upper = v.strip().upper()
            try:
                return PrimaryCategory(v_upper)
            except ValueError:
                return PrimaryCategory.OTHER
        return PrimaryCategory.OTHER

    @field_validator("article_type", mode="before")
    @classmethod
    def coerce_article_type(cls, v: str) -> ArticleType:
        if isinstance(v, str):
            v_upper = v.strip().upper()
            try:
                return ArticleType(v_upper)
            except ValueError:
                return ArticleType.OTHER
        return ArticleType.OTHER

    @field_validator("importance_score", mode="before")
    @classmethod
    def clamp_importance(cls, v: float) -> float:
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.5

    @field_validator("language", mode="before")
    @classmethod
    def clean_language(cls, v: str) -> str:
        if isinstance(v, str) and v.strip():
            return v.strip().lower()[:10]
        return "en"

    @field_validator("summary", mode="before")
    @classmethod
    def clean_summary(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return str(v)
