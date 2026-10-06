"""admin_sources.py — Phase 15 Admin Source Health Monitoring Endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.source_intelligence.source_evaluator import SourceEvaluationService
from app.source_intelligence.schemas import AdminSourceHealthResponse

router = APIRouter()


@router.get("/source-health", response_model=AdminSourceHealthResponse)
async def get_admin_source_health(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Protected admin endpoint to inspect operational health status of all sources,
    including failure counts, extraction rates, and duplicate rates.
    """
    eval_service = SourceEvaluationService(db)
    return await eval_service.get_admin_source_health()
