from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "ok"})
    service: str = Field(..., json_schema_extra={"example": "personalized-newspaper"})


class DatabaseHealthResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "connected"})
    database: str = Field(..., json_schema_extra={"example": "postgresql"})
    detail: str = Field(..., json_schema_extra={"example": "Successfully connected to PostgreSQL database."})
