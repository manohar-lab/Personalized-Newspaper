import os
from typing import List, Union, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Personalized Newspaper"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    SECRET_KEY: str = Field(default="dev-secret-key-personalized-newspaper-2026")

    # JWT Authentication Configuration
    JWT_SECRET_KEY: str = Field(default="dev-jwt-secret-key-personalized-newspaper-2026")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=10080)  # 7 days


    # API Configuration
    API_BASE_URL: str = Field(default="http://localhost:8000")
    FRONTEND_URL: str = Field(default="http://localhost:3000")
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Ingestion & Extraction Configuration
    USER_AGENT: str = Field(
        default="PersonalizedNewspaperBot/1.0 (+https://github.com/manohar-lab/Personalized-Newspaper)"
    )
    FEED_FETCH_TIMEOUT_SECONDS: int = Field(default=15)
    REQUEST_TIMEOUT: int = Field(default=15)
    MAX_CONTENT_SIZE: int = Field(default=5 * 1024 * 1024)  # 5MB
    MAX_REDIRECTS: int = Field(default=5)
    EXTRACTION_CONCURRENCY: int = Field(default=3)
    MIN_REQUEST_DELAY_SECONDS: float = Field(default=1.0)
    MIN_ARTICLE_BODY_LENGTH: int = Field(default=150)
    ROBOTS_CACHE_TTL_SECONDS: int = Field(default=3600)

    # AI Article Analysis Configuration
    AI_PROVIDER: str = Field(default="mock")  # "mock" | "openai" | "gemini"
    AI_MODEL: str = Field(default="gpt-4o-mini")
    AI_API_KEY: Optional[str] = Field(default=None)
    AI_API_BASE_URL: Optional[str] = Field(default=None)
    EMBEDDING_PROVIDER: str = Field(default="mock")  # "mock" | "openai" | "gemini"
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    MAX_ANALYSIS_CHARS: int = Field(default=12000)
    ANALYSIS_CONCURRENCY: int = Field(default=3)
    ANALYSIS_VERSION: str = Field(default="v1")

    # Personalization Engine Configuration
    PERSONALIZATION_TOPIC_WEIGHT: float = Field(default=0.30)
    PERSONALIZATION_SEMANTIC_WEIGHT: float = Field(default=0.25)
    PERSONALIZATION_ENTITY_WEIGHT: float = Field(default=0.15)
    PERSONALIZATION_KEYWORD_WEIGHT: float = Field(default=0.10)
    PERSONALIZATION_IMPORTANCE_WEIGHT: float = Field(default=0.10)
    PERSONALIZATION_RECENCY_WEIGHT: float = Field(default=0.10)

    # Negative Preferences & Decay
    NEGATIVE_TOPIC_PENALTY: float = Field(default=1.0)
    PERSONALIZATION_RECENCY_HALF_LIFE_HOURS: float = Field(default=72.0)
    PERSONALIZATION_DIVERSITY_PENALTY: float = Field(default=0.15)
    PERSONALIZATION_MAX_CONSECUTIVE_SAME_TOPIC: int = Field(default=1)

    # Automatic Interest Learning Engine Configuration
    WEIGHT_ARTICLE_OPEN: float = Field(default=0.05)
    WEIGHT_ARTICLE_READ: float = Field(default=0.10)
    WEIGHT_ARTICLE_COMPLETE: float = Field(default=0.20)
    WEIGHT_ARTICLE_LIKE: float = Field(default=0.35)
    WEIGHT_ARTICLE_SAVE: float = Field(default=0.30)
    WEIGHT_ARTICLE_SHARE: float = Field(default=0.30)
    WEIGHT_ARTICLE_NOT_INTERESTED: float = Field(default=-0.40)
    WEIGHT_ARTICLE_SKIP: float = Field(default=-0.05)
    WEIGHT_ARTICLE_IMPRESSION: float = Field(default=0.00)

    # Learning Hyperparameters
    INTEREST_LEARNING_RATE: float = Field(default=0.05)
    INTEREST_BEHAVIOR_HALF_LIFE_DAYS: float = Field(default=30.0)
    MIN_INTEREST_CONFIDENCE: float = Field(default=0.10)
    MAX_INTEREST_CONFIDENCE: float = Field(default=0.95)
    CONFIDENCE_GROWTH_RATE: float = Field(default=0.05)

    # Newspaper Generation Engine Configuration
    NEWSPAPER_PRIMARY_WINDOW_HOURS: int = Field(default=24)
    NEWSPAPER_FALLBACK_WINDOW_HOURS: int = Field(default=72)
    NEWSPAPER_EDITORIAL_RELEVANCE_WEIGHT: float = Field(default=0.60)
    NEWSPAPER_EDITORIAL_IMPORTANCE_WEIGHT: float = Field(default=0.15)
    NEWSPAPER_EDITORIAL_RECENCY_WEIGHT: float = Field(default=0.15)
    NEWSPAPER_EDITORIAL_TOPIC_CONF_WEIGHT: float = Field(default=0.10)
    NEWSPAPER_MAX_TOTAL_STORIES: int = Field(default=25)
    NEWSPAPER_LEAD_STORIES: int = Field(default=1)
    NEWSPAPER_FEATURE_STORIES: int = Field(default=4)
    NEWSPAPER_STANDARD_STORIES: int = Field(default=12)
    NEWSPAPER_COMPACT_STORIES: int = Field(default=8)
    NEWSPAPER_MAX_CONSECUTIVE_SAME_TOPIC: int = Field(default=2)
    NEWSPAPER_ENTITY_REPEAT_PENALTY: float = Field(default=0.10)
    NEWSPAPER_CLUSTER_SIMILARITY_THRESHOLD: float = Field(default=0.85)
    NEWSPAPER_DEFAULT_MASTHEAD: str = Field(default="YOUR DAILY")

    # Phase 10: Autonomous Background Pipeline & Scheduler Settings
    SCHEDULER_ENABLED: bool = Field(default=True)
    SCHEDULER_TIMEZONE: str = Field(default="UTC")
    DEFAULT_TIMEZONE: str = Field(default="Asia/Kolkata")
    NEWS_FETCH_INTERVAL_MINUTES: int = Field(default=30)
    ARTICLE_EXTRACTION_INTERVAL_MINUTES: int = Field(default=15)
    ARTICLE_ANALYSIS_INTERVAL_MINUTES: int = Field(default=15)
    EDITION_GENERATION_HOUR: int = Field(default=6)
    CLEANUP_INTERVAL_HOURS: int = Field(default=24)
    MAX_RETRY_ATTEMPTS: int = Field(default=3)
    RETRY_BACKOFF_BASE_SECONDS: int = Field(default=60)
    AI_MAX_CONCURRENCY: int = Field(default=5)
    AI_BATCH_SIZE: int = Field(default=20)
    EXTRACTION_BATCH_SIZE: int = Field(default=50)
    USER_BATCH_SIZE: int = Field(default=100)
    CLEANUP_RETENTION_DAYS: int = Field(default=30)

    # Phase 11: Intelligent Personalized Search Engine Settings
    SEARCH_FULL_TEXT_WEIGHT: float = Field(default=0.50)
    SEARCH_SEMANTIC_WEIGHT: float = Field(default=0.50)
    SEARCH_PERSONALIZATION_WEIGHT: float = Field(default=0.15)
    SEARCH_TOPIC_BOOST: float = Field(default=0.15)
    SEARCH_ENTITY_BOOST: float = Field(default=0.15)
    SEARCH_KEYWORD_BOOST: float = Field(default=0.10)
    SEARCH_DEFAULT_PAGE_SIZE: int = Field(default=20)
    SEARCH_MAX_PAGE_SIZE: int = Field(default=50)

    # Phase 12: Reading History & Engagement Intelligence System
    MINIMUM_MEANINGFUL_READ_SECONDS: float = Field(default=10.0)
    ARTICLE_COMPLETION_THRESHOLD: float = Field(default=85.0)
    ENGAGEMENT_DURATION_WEIGHT: float = Field(default=0.30)
    ENGAGEMENT_SCROLL_WEIGHT: float = Field(default=0.25)
    ENGAGEMENT_COMPLETION_WEIGHT: float = Field(default=0.25)
    ENGAGEMENT_RETURN_WEIGHT: float = Field(default=0.20)
    READING_HISTORY_RETENTION_DAYS: int = Field(default=365)
    HEARTBEAT_INTERVAL_SECONDS: int = Field(default=15)
    BOUNCE_DURATION_THRESHOLD_SECONDS: float = Field(default=10.0)
    LOW_ENGAGEMENT_THRESHOLD_SECONDS: float = Field(default=30.0)
    DEEP_READ_DURATION_SECONDS: float = Field(default=180.0)

    # Phase 13: Dynamic User Interest Intelligence Engine Settings
    INTEREST_LEARNING_INTERVAL_MINUTES: int = Field(default=30)
    INTEREST_DECAY_HALF_LIFE_DAYS: float = Field(default=30.0)
    MIN_DISCOVERY_EVIDENCE: int = Field(default=5)
    PROPAGATION_PARENT_WEIGHT: float = Field(default=0.50)
    PROPAGATION_GRANDPARENT_WEIGHT: float = Field(default=0.25)

    # Signal Weights
    SIGNAL_WEIGHT_EXPLICIT_INTEREST: float = Field(default=1.00)
    SIGNAL_WEIGHT_LIKE: float = Field(default=0.90)
    SIGNAL_WEIGHT_SAVE: float = Field(default=0.85)
    SIGNAL_WEIGHT_DEEP_READ: float = Field(default=0.75)
    SIGNAL_WEIGHT_REPEAT_READ: float = Field(default=0.80)
    SIGNAL_WEIGHT_NORMAL_READ: float = Field(default=0.35)
    SIGNAL_WEIGHT_SEARCH: float = Field(default=0.25)
    SIGNAL_WEIGHT_SHORT_READ: float = Field(default=-0.05)
    SIGNAL_WEIGHT_BOUNCE: float = Field(default=-0.10)
    SIGNAL_WEIGHT_NOT_INTERESTED: float = Field(default=-1.00)
    SIGNAL_WEIGHT_ARTICLE_IMPRESSION: float = Field(default=0.00)

    # State Thresholds
    INTEREST_STRONG_THRESHOLD: float = Field(default=0.75)
    INTEREST_STABLE_THRESHOLD: float = Field(default=0.50)
    INTEREST_DORMANT_DAYS: int = Field(default=45)

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/personalized_newspaper"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    def validate_weights(self) -> None:
        total = (
            self.PERSONALIZATION_TOPIC_WEIGHT
            + self.PERSONALIZATION_SEMANTIC_WEIGHT
            + self.PERSONALIZATION_ENTITY_WEIGHT
            + self.PERSONALIZATION_KEYWORD_WEIGHT
            + self.PERSONALIZATION_IMPORTANCE_WEIGHT
            + self.PERSONALIZATION_RECENCY_WEIGHT
        )
        if abs(total - 1.0) > 1e-5:
            raise ValueError(
                f"Personalization weights must sum to 1.0 (got {total:.4f}). "
                f"topic={self.PERSONALIZATION_TOPIC_WEIGHT}, "
                f"semantic={self.PERSONALIZATION_SEMANTIC_WEIGHT}, "
                f"entity={self.PERSONALIZATION_ENTITY_WEIGHT}, "
                f"keyword={self.PERSONALIZATION_KEYWORD_WEIGHT}, "
                f"importance={self.PERSONALIZATION_IMPORTANCE_WEIGHT}, "
                f"recency={self.PERSONALIZATION_RECENCY_WEIGHT}"
            )


settings = Settings()
settings.validate_weights()
