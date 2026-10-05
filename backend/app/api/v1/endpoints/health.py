from fastapi import APIRouter, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.health import HealthResponse, DatabaseHealthResponse
from app.database.session import check_database_connection, get_db
from app.workers.scheduler import get_scheduler_status
from app.services.news_pipeline_service import NewsPipelineService

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Get comprehensive application, database, and scheduler health status",
)
async def get_health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Returns application health status, scheduler status, and recent job timestamps."""
    db_status = await check_database_connection()
    sched_status = get_scheduler_status()
    
    last_feed = None
    last_analysis = None
    last_edition = None
    try:
        pipeline_service = NewsPipelineService(db)
        pipe_status = await pipeline_service.get_pipeline_status()
        last_feed = pipe_status.get("last_feed_run", {}).get("started_at") if pipe_status.get("last_feed_run") else None
        last_analysis = pipe_status.get("last_analysis_run", {}).get("started_at") if pipe_status.get("last_analysis_run") else None
        last_edition = pipe_status.get("last_edition_run", {}).get("started_at") if pipe_status.get("last_edition_run") else None
    except Exception:
        pass

    db_healthy = db_status.get("status") == "connected"
    is_healthy = db_healthy

    return HealthResponse(
        status="healthy" if is_healthy else "degraded",
        database="healthy" if db_healthy else "unreachable",
        scheduler="running" if sched_status.get("running") else "stopped",
        service="personalized-newspaper",
        last_feed_run=last_feed,
        last_analysis_run=last_analysis,
        last_edition_run=last_edition,
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
