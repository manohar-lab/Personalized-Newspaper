from fastapi import APIRouter, status
from app.schemas.health import HealthResponse, DatabaseHealthResponse
from app.database.session import check_database_connection

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Get basic backend service status",
)
async def get_health() -> HealthResponse:
    """Returns basic application health status."""
    return HealthResponse(
        status="ok",
        service="personalized-newspaper"
    )


@router.get(
    "/health/database",
    response_model=DatabaseHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check real PostgreSQL database connection status",
)
async def get_database_health() -> DatabaseHealthResponse:
    """Attempts to connect to PostgreSQL and returns connection status."""
    db_status = await check_database_connection()
    return DatabaseHealthResponse(
        status=db_status["status"],
        database=db_status["database"],
        detail=db_status["detail"],
    )
