import os
from typing import List, Union
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


settings = Settings()
