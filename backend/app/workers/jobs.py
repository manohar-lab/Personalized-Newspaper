"""jobs.py — Phase 10 Autonomous Worker Job Handlers."""
import logging
from typing import Any, Dict
from app.database.session import AsyncSessionLocal
from app.services.news_pipeline_service import NewsPipelineService

logger = logging.getLogger(__name__)


async def job_fetch_feeds() -> Dict[str, Any]:
    """Background job 1: Ingest active RSS/Atom feeds."""
    logger.info("Executing scheduled job: fetch_feeds")
    async with AsyncSessionLocal() as session:
        service = NewsPipelineService(session)
        res = await service.run_fetch_feeds()
        logger.info(f"Finished fetch_feeds: status={res.get('status')}")
        return res


async def job_extract_pending() -> Dict[str, Any]:
    """Background job 2: Web extract content for pending articles."""
    logger.info("Executing scheduled job: extract_pending")
    async with AsyncSessionLocal() as session:
        service = NewsPipelineService(session)
        res = await service.run_extract_pending_articles()
        logger.info(f"Finished extract_pending: status={res.get('status')}")
        return res


async def job_analyze_pending() -> Dict[str, Any]:
    """Background job 3: Analyze pending articles with AI."""
    logger.info("Executing scheduled job: analyze_pending")
    async with AsyncSessionLocal() as session:
        service = NewsPipelineService(session)
        res = await service.run_analyze_pending_articles()
        logger.info(f"Finished analyze_pending: status={res.get('status')}")
        return res


async def job_generate_daily_editions() -> Dict[str, Any]:
    """Background job 4: Generate daily newspaper editions for active users."""
    logger.info("Executing scheduled job: generate_daily_editions")
    async with AsyncSessionLocal() as session:
        service = NewsPipelineService(session)
        res = await service.run_generate_daily_editions()
        logger.info(f"Finished generate_daily_editions: status={res.get('status')}")
        return res


async def job_cleanup_old_data() -> Dict[str, Any]:
    """Background job 5: Clean up old temporary logs."""
    logger.info("Executing scheduled job: cleanup_old_data")
    async with AsyncSessionLocal() as session:
        service = NewsPipelineService(session)
        res = await service.run_cleanup_old_data()
        logger.info(f"Finished cleanup_old_data: status={res.get('status')}")
        return res


async def job_full_pipeline() -> Dict[str, Any]:
    """Background job: Run full end-to-end pipeline."""
    logger.info("Executing full autonomous pipeline")
    async with AsyncSessionLocal() as session:
        service = NewsPipelineService(session)
        res = await service.run_full_autonomous_pipeline()
        logger.info(f"Finished full pipeline: status={res.get('status')}")
        return res
