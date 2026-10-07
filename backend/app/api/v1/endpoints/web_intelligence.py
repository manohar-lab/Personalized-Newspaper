"""web_intelligence.py — Phase 20 Real Web Intelligence & Source Ingestion Admin Endpoints.

Provides APIs for testing live source feeds, running extraction diagnostics on target URLs,
and monitoring ingestion pipeline health and data quality.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.extraction.fetcher import FetchError, SSRFValidationError, WebPageFetcher
from app.extraction.models import ExtractionStatus, RobotsAccess
from app.extraction.robots import RobotsChecker
from app.extraction.sources.registry import extractor_registry
from app.extraction.url_normalizer import URLNormalizer
from app.models.article import Article
from app.models.feed import NewsFeed
from app.models.ingestion_job import IngestionJob
from app.models.source import NewsSource
from app.services.robust_ingestion_service import RobustIngestionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Web Intelligence & Ingestion"])


# -----------------------------------------------------------------------------
# SCHEMAS
# -----------------------------------------------------------------------------
class ArticleExtractionTestRequest(BaseModel):
    url: str


class ArticleExtractionTestResponse(BaseModel):
    url: str
    final_url: str
    canonical_url: str
    http_status: int
    robots_status: str
    extraction_status: str
    title: Optional[str] = None
    headline: Optional[str] = None
    author: Optional[str] = None
    publication_date: Optional[datetime] = None
    image_url: Optional[str] = None
    content_length: int = 0
    reading_time_minutes: int = 1
    quality_score: float = 0.0
    quality_flags: List[str] = []
    error_message: Optional[str] = None
    is_safe: bool = True
    snippet: Optional[str] = None


class SourceTestResponse(BaseModel):
    source_id: str
    source_name: str
    domain: Optional[str]
    robots_status: str
    feed_count: int
    tested_feeds: List[Dict[str, Any]]
    sample_article: Optional[Dict[str, Any]] = None
    health_status: str
    success: bool


# -----------------------------------------------------------------------------
# ENDPOINTS
# -----------------------------------------------------------------------------
@router.post(
    "/extraction/test",
    response_model=ArticleExtractionTestResponse,
    summary="Test article extraction on any URL safely",
)
async def test_article_extraction(
    payload: ArticleExtractionTestRequest,
) -> ArticleExtractionTestResponse:
    """Safely test URL fetching, robots compliance, and extraction quality diagnostics."""
    target_url = payload.url.strip()
    if not target_url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    # 1. SSRF Safety check
    is_safe, reason = WebPageFetcher.is_ssrf_safe_url(target_url)
    if not is_safe:
        return ArticleExtractionTestResponse(
            url=target_url,
            final_url=target_url,
            canonical_url=target_url,
            http_status=400,
            robots_status="UNKNOWN",
            extraction_status="FAILED",
            is_safe=False,
            error_message=f"SSRF safety rejection: {reason}",
        )

    fetcher = WebPageFetcher()
    robots_checker = RobotsChecker()

    # 2. Check robots.txt
    robots_access = await robots_checker.check_access(target_url)
    robots_status_str = robots_access.value

    if robots_access == RobotsAccess.DISALLOWED:
        return ArticleExtractionTestResponse(
            url=target_url,
            final_url=target_url,
            canonical_url=URLNormalizer.normalize_url(target_url),
            http_status=200,
            robots_status=robots_status_str,
            extraction_status="ROBOTS_BLOCKED",
            error_message="Access disallowed by publisher robots.txt",
        )

    # 3. Safe Fetch
    try:
        fetch_res = await fetcher.fetch_safe(target_url)
    except SSRFValidationError as ssrf_err:
        return ArticleExtractionTestResponse(
            url=target_url,
            final_url=target_url,
            canonical_url=target_url,
            http_status=400,
            robots_status=robots_status_str,
            extraction_status="FAILED",
            is_safe=False,
            error_message=f"SSRF violation: {ssrf_err}",
        )
    except FetchError as fetch_err:
        return ArticleExtractionTestResponse(
            url=target_url,
            final_url=target_url,
            canonical_url=URLNormalizer.normalize_url(target_url),
            http_status=fetch_err.status_code or 500,
            robots_status=robots_status_str,
            extraction_status="FAILED",
            error_message=str(fetch_err),
        )
    except Exception as exc:
        return ArticleExtractionTestResponse(
            url=target_url,
            final_url=target_url,
            canonical_url=URLNormalizer.normalize_url(target_url),
            http_status=500,
            robots_status=robots_status_str,
            extraction_status="FAILED",
            error_message=f"Unexpected error: {exc}",
        )

    # 4. Extract with appropriate registered source extractor
    extractor = extractor_registry.get_extractor(target_url)
    extracted = extractor.extract(fetch_res.html, fetch_res.final_url or target_url)

    snippet = None
    if extracted.content:
        snippet = extracted.content[:300] + ("..." if len(extracted.content) > 300 else "")
    elif extracted.description:
        snippet = extracted.description

    quality_flags = []
    if extracted.quality_breakdown:
        quality_flags = extracted.quality_breakdown.flags

    return ArticleExtractionTestResponse(
        url=target_url,
        final_url=fetch_res.final_url,
        canonical_url=extracted.canonical_url or URLNormalizer.normalize_url(target_url),
        http_status=fetch_res.status_code,
        robots_status=robots_status_str,
        extraction_status=extracted.status.value,
        title=extracted.title,
        headline=extracted.headline or extracted.title,
        author=extracted.author,
        publication_date=extracted.publication_date,
        image_url=extracted.image_url,
        content_length=extracted.content_length,
        reading_time_minutes=extracted.reading_time_minutes,
        quality_score=extracted.quality_score,
        quality_flags=quality_flags,
        error_message=extracted.error_message,
        is_safe=True,
        snippet=snippet,
    )


@router.post(
    "/news/sources/{source_id}/test",
    response_model=SourceTestResponse,
    summary="Test news source feeds and sample extraction diagnostics",
)
async def test_source_feeds(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SourceTestResponse:
    """Test all feeds belonging to a source, testing robots.txt and sample parsing without permanently modifying data."""
    stmt = select(NewsSource).where(NewsSource.id == source_id)
    res = await db.execute(stmt)
    source = res.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="News source not found")

    feed_stmt = select(NewsFeed).where(NewsFeed.source_id == source_id)
    feed_res = await db.execute(feed_stmt)
    feeds = list(feed_res.scalars().all())

    service = RobustIngestionService(session=db)
    tested_feeds = []
    all_success = True

    for f in feeds:
        feed_test_res = await service.ingest_feed(f, force_fetch=True)
        tested_feeds.append(feed_test_res)
        if feed_test_res.get("status") == "FAILED":
            all_success = False

    domain = source.domain or URLNormalizer.extract_domain(source.website_url)
    robots_access = await service.robots_checker.check_access(source.website_url)

    return SourceTestResponse(
        source_id=str(source.id),
        source_name=source.name,
        domain=domain,
        robots_status=robots_access.value,
        feed_count=len(feeds),
        tested_feeds=tested_feeds,
        health_status="HEALTHY" if all_success else "DEGRADED",
        success=all_success,
    )


@router.get(
    "/admin/sources/monitoring",
    summary="Get comprehensive source health, feed metrics, and ingestion diagnostics",
)
async def get_source_monitoring_dashboard(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Admin dashboard data aggregating sources, feeds, jobs, and extraction quality metrics."""
    # 1. Total counts
    sources_res = await db.execute(select(NewsSource))
    sources = list(sources_res.scalars().all())

    feeds_res = await db.execute(select(NewsFeed))
    feeds = list(feeds_res.scalars().all())

    # 2. Source health distribution
    health_counts = {"HEALTHY": 0, "DEGRADED": 0, "FAILING": 0, "BLOCKED": 0, "DISABLED": 0}
    for s in sources:
        h = s.health_status or "HEALTHY"
        health_counts[h] = health_counts.get(h, 0) + 1

    # 3. Article Extraction Metrics
    article_stats_query = select(
        Article.extraction_status, func.count(Article.id)
    ).group_by(Article.extraction_status)
    art_stats_res = await db.execute(article_stats_query)
    extraction_distribution = {status: count for status, count in art_stats_res.all()}

    # 4. Ingestion Jobs
    jobs_query = select(IngestionJob).order_by(IngestionJob.started_at.desc()).limit(10)
    jobs_res = await db.execute(jobs_query)
    recent_jobs = [
        {
            "id": str(j.id),
            "job_type": j.job_type,
            "status": j.status,
            "started_at": j.started_at,
            "completed_at": j.completed_at,
            "items_processed": j.items_processed,
            "items_created": j.items_created,
            "items_updated": j.items_updated,
            "items_failed": j.items_failed,
            "error_message": j.error_message,
        }
        for j in jobs_res.scalars().all()
    ]

    return {
        "summary": {
            "total_sources": len(sources),
            "total_feeds": len(feeds),
            "healthy_sources": health_counts.get("HEALTHY", 0),
            "degraded_sources": health_counts.get("DEGRADED", 0),
            "failing_sources": health_counts.get("FAILING", 0),
            "blocked_sources": health_counts.get("BLOCKED", 0),
        },
        "sources": [
            {
                "id": str(s.id),
                "name": s.name,
                "domain": s.domain or URLNormalizer.extract_domain(s.website_url),
                "website_url": s.website_url,
                "health_status": s.health_status,
                "quality_score": round(s.quality_score, 2),
                "robots_status": s.robots_status,
                "success_count": s.success_count,
                "failure_count": s.failure_count,
                "last_success_at": s.last_success_at,
                "last_failure_at": s.last_failure_at,
            }
            for s in sources
        ],
        "feeds": [
            {
                "id": str(f.id),
                "name": f.name,
                "feed_url": f.feed_url,
                "source_id": str(f.source_id),
                "health_status": f.health_status,
                "http_status": f.http_status,
                "etag": f.etag,
                "last_modified": f.last_modified,
                "last_fetched_at": f.last_fetched_at,
                "last_success_at": f.last_success_at,
            }
            for f in feeds
        ],
        "extraction_distribution": extraction_distribution,
        "recent_jobs": recent_jobs,
    }


@router.post(
    "/admin/ingestion/run",
    summary="Trigger an autonomous robust ingestion run across all active feeds",
)
async def trigger_ingestion_run(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Execute a robust ingestion run with bounded worker pool and conditional requests."""
    service = RobustIngestionService(session=db)
    job = await service.run_ingestion_pipeline(max_feeds=25)
    return {
        "job_id": str(job.id),
        "status": job.status,
        "items_processed": job.items_processed,
        "items_created": job.items_created,
        "items_updated": job.items_updated,
        "items_failed": job.items_failed,
    }
