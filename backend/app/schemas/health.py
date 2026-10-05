from typing import Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", json_schema_extra={"example": "healthy"})
    database: Optional[str] = Field(default="healthy", json_schema_extra={"example": "healthy"})
    scheduler: Optional[str] = Field(default="running", json_schema_extra={"example": "running"})
    service: Optional[str] = Field(default="personalized-newspaper", json_schema_extra={"example": "personalized-newspaper"})
    last_feed_run: Optional[Any] = None
    last_analysis_run: Optional[Any] = None
    last_edition_run: Optional[Any] = None


class DatabaseHealthResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "connected"})
    database: str = Field(..., json_schema_extra={"example": "postgresql"})
    detail: str = Field(..., json_schema_extra={"example": "Successfully connected to PostgreSQL database."})
