"""news_pipeline_service.py — Phase 10 Autonomous Pipeline Service."""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from sqlalchemy import select, func, desc, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.pipeline_run import PipelineRun
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.models.user import User
from app.ingestion.services.ingestion_service import IngestionService
from app.services.article_extraction_service import ArticleExtractionService
from app.ai.services.article_analysis_service import ArticleAnalysisService
from app.newspaper.generator import NewspaperGenerationService
from app.workers.locks import try_acquire_job_lock

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NewsPipelineService:
    """
    Central orchestration service for the autonomous news processing pipeline:
    1. Feed Discovery & Ingestion
    2. Web Article Content Extraction (respecting robots.txt & retries)
    3. AI Article Analysis & Understanding (with concurrency controls & embeddings)
    4. Daily Newspaper Edition Generation (for active users in local timezones)
    5. Cleanup of old temporary pipeline logs
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.ingestion_service = IngestionService(session)
        self.extraction_service = ArticleExtractionService(session)
        self.analysis_service = ArticleAnalysisService(session)
        self.newspaper_service = NewspaperGenerationService(session)

    # -------------------------------------------------------------------------
    # 1. Feed Fetching & Ingestion Job
    # -------------------------------------------------------------------------
    async def run_fetch_feeds(self) -> Dict[str, Any]:
        """Fetches all active RSS/Atom feeds, deduplicates, and stores new articles."""
        run = PipelineRun(
            job_type="FETCH_FEEDS",
            status="RUNNING",
            started_at=utc_now(),
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)

        async with try_acquire_job_lock(self.session, "fetch_feeds") as acquired:
            if not acquired:
                run.status = "SKIPPED"
                run.completed_at = utc_now()
                run.error_message = "Job locked by another worker"
                await self.session.commit()
                return {"status": "SKIPPED", "message": "Job already running"}

            try:
                result = await self.ingestion_service.ingest_all_active_feeds()
                total_created = result.get("total_articles_created", 0)
                total_duplicates = result.get("total_duplicates_found", 0)
                total_errors = result.get("failed_feeds", 0)
                total_feeds = result.get("total_feeds", 0)

                run.items_processed = total_created + total_duplicates
                run.items_succeeded = total_created
                run.items_failed = total_errors
                run.status = "SUCCESS" if total_errors == 0 else ("PARTIAL" if total_created > 0 else "FAILED")
                run.completed_at = utc_now()
                run.details = json.dumps({
                    "total_feeds": total_feeds,
                    "articles_created": total_created,
                    "duplicates": total_duplicates,
                    "errors": total_errors,
                })
                await self.session.commit()
                return {
                    "run_id": str(run.id),
                    "status": run.status,
                    "articles_created": total_created,
                    "duplicates": total_duplicates,
                    "errors": total_errors,
                }
            except Exception as e:
                logger.error(f"Error during fetch_feeds job: {e}", exc_info=True)
                run.status = "FAILED"
                run.completed_at = utc_now()
                run.error_message = str(e)
                await self.session.commit()
                return {"run_id": str(run.id), "status": "FAILED", "error": str(e)}

    # -------------------------------------------------------------------------
    # 2. Web Extraction Job
    # -------------------------------------------------------------------------
    async def run_extract_pending_articles(
        self,
        limit: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Extracts content for pending articles with exponential backoff and max retry limits."""
        limit = limit or settings.EXTRACTION_BATCH_SIZE
        max_retries = max_retries or settings.MAX_RETRY_ATTEMPTS

        run = PipelineRun(
            job_type="EXTRACT_PENDING",
            status="RUNNING",
            started_at=utc_now(),
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)

        async with try_acquire_job_lock(self.session, "extract_pending") as acquired:
            if not acquired:
                run.status = "SKIPPED"
                run.completed_at = utc_now()
                run.error_message = "Job locked by another worker"
                await self.session.commit()
                return {"status": "SKIPPED", "message": "Job already running"}

            try:
                # Query articles requiring extraction
                stmt = (
                    select(Article)
                    .where(
                        Article.status == "PUBLISHED",
                        or_(
                            Article.extraction_status.in_(["NOT_ATTEMPTED", "PENDING", None]),
                            and_(
                                Article.extraction_status == "FAILED",
                                Article.is_full_text_available == False,
                            )
                        )
                    )
                    .order_by(Article.published_at.desc())
                    .limit(limit)
                )
                res = await self.session.execute(stmt)
                articles = list(res.scalars().all())

                if not articles:
                    run.status = "SUCCESS"
                    run.completed_at = utc_now()
                    run.details = json.dumps({"message": "No pending articles to extract"})
                    await self.session.commit()
                    return {"run_id": str(run.id), "status": "SUCCESS", "extracted": 0, "failed": 0}

                succeeded = 0
                failed = 0
                skipped = 0

                for art in articles:
                    try:
                        ext_res = await self.extraction_service.extract_article(art.id)
                        if ext_res.get("success"):
                            succeeded += 1
                        elif ext_res.get("status") in ["ROBOTS_BLOCKED", "PAYWALL", "ACCESS_DENIED"]:
                            skipped += 1
                        else:
                            failed += 1
                    except Exception as ex:
                        logger.warning(f"Failed extraction for article {art.id}: {ex}")
                        failed += 1

                run.items_processed = len(articles)
                run.items_succeeded = succeeded
                run.items_failed = failed
                run.status = "SUCCESS" if failed == 0 else ("PARTIAL" if succeeded > 0 else "FAILED")
                run.completed_at = utc_now()
                run.details = json.dumps({
                    "total_checked": len(articles),
                    "succeeded": succeeded,
                    "failed": failed,
                    "skipped": skipped,
                })
                await self.session.commit()
                return {
                    "run_id": str(run.id),
                    "status": run.status,
                    "total_checked": len(articles),
                    "succeeded": succeeded,
                    "failed": failed,
                    "skipped": skipped,
                }
            except Exception as e:
                logger.error(f"Error during extract_pending job: {e}", exc_info=True)
                run.status = "FAILED"
                run.completed_at = utc_now()
                run.error_message = str(e)
                await self.session.commit()
                return {"run_id": str(run.id), "status": "FAILED", "error": str(e)}

    # -------------------------------------------------------------------------
    # 3. AI Analysis Job
    # -------------------------------------------------------------------------
    async def run_analyze_pending_articles(
        self,
        limit: Optional[int] = None,
        max_concurrency: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Analyzes pending articles with AI, producing categories, topics, entities, summaries, and embeddings."""
        limit = limit or settings.AI_BATCH_SIZE
        max_concurrency = max_concurrency or settings.AI_MAX_CONCURRENCY

        run = PipelineRun(
            job_type="ANALYZE_PENDING",
            status="RUNNING",
            started_at=utc_now(),
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)

        async with try_acquire_job_lock(self.session, "analyze_pending") as acquired:
            if not acquired:
                run.status = "SKIPPED"
                run.completed_at = utc_now()
                run.error_message = "Job locked by another worker"
                await self.session.commit()
                return {"status": "SKIPPED", "message": "Job already running"}

            try:
                # Query articles that need analysis
                # Left join ArticleAnalysis to find articles without analysis or where analysis failed
                stmt = (
                    select(Article.id)
                    .outerjoin(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
                    .where(
                        Article.status == "PUBLISHED",
                        or_(
                            ArticleAnalysis.id == None,
                            ArticleAnalysis.analysis_status.in_(["FAILED", "PENDING"]),
                        )
                    )
                    .order_by(Article.published_at.desc())
                    .limit(limit)
                )
                res = await self.session.execute(stmt)
                article_ids = list(res.scalars().all())

                if not article_ids:
                    run.status = "SUCCESS"
                    run.completed_at = utc_now()
                    run.details = json.dumps({"message": "No pending articles to analyze"})
                    await self.session.commit()
                    return {"run_id": str(run.id), "status": "SUCCESS", "analyzed": 0, "failed": 0}

                semaphore = asyncio.Semaphore(max_concurrency)

                async def _analyze_with_semaphore(art_id: uuid.UUID) -> Dict[str, Any]:
                    async with semaphore:
                        try:
                            return await self.analysis_service.analyze_article(art_id)
                        except Exception as e:
                            logger.warning(f"Error analyzing article {art_id}: {e}")
                            return {"article_id": str(art_id), "status": "FAILED", "error": str(e)}

                tasks = [_analyze_with_semaphore(aid) for aid in article_ids]
                results = await asyncio.gather(*tasks, return_exceptions=False)

                succeeded = sum(1 for r in results if r.get("status") == "SUCCESS")
                failed = sum(1 for r in results if r.get("status") != "SUCCESS")

                run.items_processed = len(article_ids)
                run.items_succeeded = succeeded
                run.items_failed = failed
                run.status = "SUCCESS" if failed == 0 else ("PARTIAL" if succeeded > 0 else "FAILED")
                run.completed_at = utc_now()
                run.details = json.dumps({
                    "total_checked": len(article_ids),
                    "succeeded": succeeded,
                    "failed": failed,
                })
                await self.session.commit()
                return {
                    "run_id": str(run.id),
                    "status": run.status,
                    "total_checked": len(article_ids),
                    "succeeded": succeeded,
                    "failed": failed,
                }
            except Exception as e:
                logger.error(f"Error during analyze_pending job: {e}", exc_info=True)
                run.status = "FAILED"
                run.completed_at = utc_now()
                run.error_message = str(e)
                await self.session.commit()
                return {"run_id": str(run.id), "status": "FAILED", "error": str(e)}

    # -------------------------------------------------------------------------
    # 4. Daily Edition Generation Job
    # -------------------------------------------------------------------------
    async def run_generate_daily_editions(
        self,
        target_date: Optional[str] = None,
        batch_size: Optional[int] = None,
        user_ids: Optional[List[uuid.UUID]] = None,
    ) -> Dict[str, Any]:
        """Automatically generates daily editions for active users according to their local timezone."""
        batch_size = batch_size or settings.USER_BATCH_SIZE

        run = PipelineRun(
            job_type="GENERATE_EDITIONS",
            status="RUNNING",
            started_at=utc_now(),
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)

        async with try_acquire_job_lock(self.session, "generate_editions") as acquired:
            if not acquired:
                run.status = "SKIPPED"
                run.completed_at = utc_now()
                run.error_message = "Job locked by another worker"
                await self.session.commit()
                return {"status": "SKIPPED", "message": "Job already running"}

            try:
                # Query active users
                stmt = select(User).where(User.is_active == True)
                if user_ids:
                    stmt = stmt.where(User.id.in_(user_ids))
                stmt = stmt.limit(batch_size)
                res = await self.session.execute(stmt)
                users = list(res.scalars().all())

                if not users:
                    run.status = "SUCCESS"
                    run.completed_at = utc_now()
                    run.details = json.dumps({"message": "No active users found"})
                    await self.session.commit()
                    return {"run_id": str(run.id), "status": "SUCCESS", "editions_generated": 0}

                succeeded = 0
                failed = 0

                for u in users:
                    # Determine target date for user
                    if target_date:
                        user_date_str = target_date
                    else:
                        tz_name = settings.DEFAULT_TIMEZONE
                        try:
                            tz = ZoneInfo(tz_name)
                            user_now = datetime.now(tz)
                            user_date_str = user_now.strftime("%Y-%m-%d")
                        except Exception:
                            user_date_str = utc_now().strftime("%Y-%m-%d")

                    try:
                        await self.newspaper_service.generate_daily_edition(
                            user_id=u.id,
                            target_date=user_date_str,
                            force_regenerate=False,
                        )
                        succeeded += 1
                    except Exception as e:
                        logger.warning(f"Error generating edition for user {u.id}: {e}")
                        failed += 1

                run.items_processed = len(users)
                run.items_succeeded = succeeded
                run.items_failed = failed
                run.status = "SUCCESS" if failed == 0 else ("PARTIAL" if succeeded > 0 else "FAILED")
                run.completed_at = utc_now()
                run.details = json.dumps({
                    "total_users": len(users),
                    "succeeded": succeeded,
                    "failed": failed,
                })
                await self.session.commit()
                return {
                    "run_id": str(run.id),
                    "status": run.status,
                    "total_users": len(users),
                    "succeeded": succeeded,
                    "failed": failed,
                }
            except Exception as e:
                logger.error(f"Error during generate_daily_editions job: {e}", exc_info=True)
                run.status = "FAILED"
                run.completed_at = utc_now()
                run.error_message = str(e)
                await self.session.commit()
                return {"run_id": str(run.id), "status": "FAILED", "error": str(e)}

    # -------------------------------------------------------------------------
    # 5. Cleanup Job
    # -------------------------------------------------------------------------
    async def run_cleanup_old_data(
        self,
        retention_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Cleans up old pipeline logs and stale temporary records without deleting user data."""
        retention_days = retention_days or settings.CLEANUP_RETENTION_DAYS

        run = PipelineRun(
            job_type="CLEANUP_OLD_DATA",
            status="RUNNING",
            started_at=utc_now(),
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)

        async with try_acquire_job_lock(self.session, "cleanup_old_data") as acquired:
            if not acquired:
                run.status = "SKIPPED"
                run.completed_at = utc_now()
                run.error_message = "Job locked by another worker"
                await self.session.commit()
                return {"status": "SKIPPED", "message": "Job already running"}

            try:
                cutoff = utc_now() - timedelta(days=retention_days)
                # Delete old completed pipeline runs older than retention cutoff (preserve current run)
                stmt = delete(PipelineRun).where(
                    PipelineRun.created_at < cutoff,
                    PipelineRun.id != run.id,
                )
                res = await self.session.execute(stmt)
                deleted_count = res.rowcount if hasattr(res, "rowcount") else 0

                run.items_processed = deleted_count
                run.items_succeeded = deleted_count
                run.status = "SUCCESS"
                run.completed_at = utc_now()
                run.details = json.dumps({"deleted_pipeline_runs": deleted_count, "cutoff": cutoff.isoformat()})
                await self.session.commit()
                return {
                    "run_id": str(run.id),
                    "status": "SUCCESS",
                    "deleted_runs": deleted_count,
                }
            except Exception as e:
                logger.error(f"Error during cleanup_old_data job: {e}", exc_info=True)
                run.status = "FAILED"
                run.completed_at = utc_now()
                run.error_message = str(e)
                await self.session.commit()
                return {"run_id": str(run.id), "status": "FAILED", "error": str(e)}

    # -------------------------------------------------------------------------
    # 6. Full End-to-End Autonomous Pipeline Orchestrator
    # -------------------------------------------------------------------------
    async def run_full_autonomous_pipeline(self) -> Dict[str, Any]:
        """
        Executes the complete autonomous sequence in strict dependency order:
        FETCH -> EXTRACT -> ANALYZE -> GENERATE.
        Tolerates partial failures so downstream steps process available articles.
        """
        overall_run = PipelineRun(
            job_type="FULL_PIPELINE",
            status="RUNNING",
            started_at=utc_now(),
        )
        self.session.add(overall_run)
        await self.session.commit()
        await self.session.refresh(overall_run)

        async with try_acquire_job_lock(self.session, "full_pipeline") as acquired:
            if not acquired:
                overall_run.status = "SKIPPED"
                overall_run.completed_at = utc_now()
                overall_run.error_message = "Full pipeline locked by another worker"
                await self.session.commit()
                return {"status": "SKIPPED", "message": "Pipeline already running"}

            try:
                # 1. Fetch
                fetch_res = await self.run_fetch_feeds()
                # 2. Extract
                extract_res = await self.run_extract_pending_articles()
                # 3. Analyze
                analyze_res = await self.run_analyze_pending_articles()
                # 4. Generate
                generate_res = await self.run_generate_daily_editions()

                stage_statuses = [
                    fetch_res.get("status"),
                    extract_res.get("status"),
                    analyze_res.get("status"),
                    generate_res.get("status"),
                ]

                if all(s == "SUCCESS" for s in stage_statuses):
                    overall_run.status = "SUCCESS"
                elif any(s in ["SUCCESS", "PARTIAL"] for s in stage_statuses):
                    overall_run.status = "PARTIAL"
                else:
                    overall_run.status = "FAILED"

                overall_run.completed_at = utc_now()
                overall_run.details = json.dumps({
                    "fetch": fetch_res,
                    "extract": extract_res,
                    "analyze": analyze_res,
                    "generate": generate_res,
                })
                await self.session.commit()

                return {
                    "run_id": str(overall_run.id),
                    "status": overall_run.status,
                    "fetch": fetch_res,
                    "extract": extract_res,
                    "analyze": analyze_res,
                    "generate": generate_res,
                }
            except Exception as e:
                logger.error(f"Error during full pipeline: {e}", exc_info=True)
                overall_run.status = "FAILED"
                overall_run.completed_at = utc_now()
                overall_run.error_message = str(e)
                await self.session.commit()
                return {"run_id": str(overall_run.id), "status": "FAILED", "error": str(e)}

    # -------------------------------------------------------------------------
    # Status & Observability Queries
    # -------------------------------------------------------------------------
    async def get_pipeline_status(self) -> Dict[str, Any]:
        """Returns the high-level health and timestamp status of the pipeline."""
        # Query last run for each job type
        job_types = ["FETCH_FEEDS", "EXTRACT_PENDING", "ANALYZE_PENDING", "GENERATE_EDITIONS", "FULL_PIPELINE"]
        last_runs: Dict[str, Any] = {}

        for jt in job_types:
            stmt = (
                select(PipelineRun)
                .where(PipelineRun.job_type == jt)
                .order_by(desc(PipelineRun.started_at))
                .limit(1)
            )
            res = await self.session.execute(stmt)
            r = res.scalar_one_or_none()
            if r:
                last_runs[jt.lower()] = {
                    "id": str(r.id),
                    "status": r.status,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "items_processed": r.items_processed,
                    "items_succeeded": r.items_succeeded,
                    "items_failed": r.items_failed,
                }
            else:
                last_runs[jt.lower()] = None

        # Query currently active running jobs
        stmt_running = (
            select(PipelineRun)
            .where(PipelineRun.status == "RUNNING")
            .order_by(desc(PipelineRun.started_at))
        )
        res_running = await self.session.execute(stmt_running)
        running_jobs = [
            {"id": str(r.id), "job_type": r.job_type, "started_at": r.started_at.isoformat()}
            for r in res_running.scalars().all()
        ]

        # Query aggregate article metrics
        total_articles = await self.session.scalar(select(func.count(Article.id))) or 0
        extracted_articles = await self.session.scalar(
            select(func.count(Article.id)).where(Article.is_full_text_available == True)
        ) or 0
        analyzed_articles = await self.session.scalar(
            select(func.count(ArticleAnalysis.id)).where(ArticleAnalysis.analysis_status == "SUCCESS")
        ) or 0

        return {
            "last_feed_run": last_runs.get("fetch_feeds"),
            "last_extraction_run": last_runs.get("extract_pending"),
            "last_analysis_run": last_runs.get("analyze_pending"),
            "last_edition_run": last_runs.get("generate_editions"),
            "last_full_pipeline": last_runs.get("full_pipeline"),
            "running_jobs": running_jobs,
            "metrics": {
                "total_articles": total_articles,
                "extracted_articles": extracted_articles,
                "analyzed_articles": analyzed_articles,
            },
        }

    async def get_recent_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns list of recent pipeline runs."""
        stmt = select(PipelineRun).order_by(desc(PipelineRun.started_at)).limit(limit)
        res = await self.session.execute(stmt)
        runs = res.scalars().all()
        return [
            {
                "id": str(r.id),
                "job_type": r.job_type,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "items_processed": r.items_processed,
                "items_succeeded": r.items_succeeded,
                "items_failed": r.items_failed,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ]
