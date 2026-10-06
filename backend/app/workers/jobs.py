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


async def job_interest_learning() -> Dict[str, Any]:
    """Background job 6: Phase 13 Batch user dynamic interest learning."""
    logger.info("Executing scheduled job: interest_learning")
    from app.ai.interests.learner import InterestLearningService
    async with AsyncSessionLocal() as session:
        learner = InterestLearningService(session)
        count = await learner.process_unprocessed_events()
        logger.info(f"Finished interest_learning: processed={count} events")
        return {"status": "success", "processed_events": count}


async def job_generate_recommendations() -> Dict[str, Any]:
    """Background job 7: Phase 14 Batch background recommendation candidate generation for active users."""
    logger.info("Executing scheduled job: generate_recommendations")
    from sqlalchemy import select
    from app.models.user import User
    from app.recommendations.recommendation_service import RecommendationService

    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.is_active.is_(True))
        res = await session.execute(stmt)
        active_users = list(res.scalars().all())

        rec_service = RecommendationService(session)
        processed_count = 0
        for user in active_users:
            try:
                await rec_service.recommend(
                    user_id=user.id,
                    limit=20,
                    context="DISCOVER",
                    force_refresh=True,
                )
                processed_count += 1
            except Exception as e:
                logger.warning(f"Error generating background recommendations for user {user.id}: {e}")

        logger.info(f"Finished generate_recommendations: processed={processed_count} active users")
        return {"status": "success", "processed_users": processed_count}


async def job_full_pipeline() -> Dict[str, Any]:
    """Background job: Run full end-to-end pipeline."""
    logger.info("Executing full autonomous pipeline")
    async with AsyncSessionLocal() as session:
        service = NewsPipelineService(session)
        res = await service.run_full_autonomous_pipeline()
        logger.info(f"Finished full pipeline: status={res.get('status')}")
        return res

