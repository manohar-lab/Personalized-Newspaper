import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user, get_optional_current_user
from app.models.user import User
from app.models.ingestion_run import IngestionRun
from app.ingestion.services.source_service import SourceService
from app.ingestion.services.ingestion_service import IngestionService
from app.ingestion.scraper.scraper_service import ScraperService
from app.services.article_extraction_service import ArticleExtractionService
from app.models.article import Article
from app.schemas.news import (
    SourceCreate,
    SourceResponse,
    FeedCreate,
    FeedResponse,
    FeedTestResponse,
    IngestionRunResponse,
    IngestionSummary,
    IngestionBatchResponse,
    ScrapeArticleResponse,
    ScrapeBatchResponse,
    ExtractionResultResponse,
    ExtractPendingResponse,
    ExtractionStatusDetailResponse,
)

router = APIRouter()


@router.get("/sources", response_model=List[SourceResponse])
async def get_sources(
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List all news sources and their active feeds.
    """
    service = SourceService(db)
    sources = await service.get_sources(is_active=is_active)
    
    response = []
    for s in sources:
        response.append(
            SourceResponse(
                id=s.id,
                name=s.name,
                slug=s.slug,
                website_url=s.website_url,
                description=s.description,
                logo_url=s.logo_url,
                is_active=s.is_active,
                created_at=s.created_at,
                updated_at=s.updated_at,
                feeds_count=len(s.feeds) if s.feeds else 0,
            )
        )
    return response


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new news source (Requires authentication).
    """
    service = SourceService(db)
    existing = await service.get_source_by_slug(payload.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source with slug '{payload.slug}' already exists.",
        )
    
    source = await service.create_source(payload)
    return SourceResponse(
        id=source.id,
        name=source.name,
        slug=source.slug,
        website_url=source.website_url,
        description=source.description,
        logo_url=source.logo_url,
        is_active=source.is_active,
        created_at=source.created_at,
        updated_at=source.updated_at,
        feeds_count=0,
    )


@router.get("/feeds", response_model=List[FeedResponse])
async def get_feeds(
    source_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List all RSS/Atom feeds with status and source info.
    """
    service = SourceService(db)
    feeds = await service.get_feeds(is_active=is_active, source_id=source_id)

    response = []
    for f in feeds:
        response.append(
            FeedResponse(
                id=f.id,
                source_id=f.source_id,
                source_name=f.source.name if f.source else None,
                name=f.name,
                feed_url=f.feed_url,
                feed_type=f.feed_type,
                language=f.language,
                is_active=f.is_active,
                default_topic_id=f.default_topic_id,
                default_topic_name=f.default_topic.name if f.default_topic else None,
                last_fetched_at=f.last_fetched_at,
                last_success_at=f.last_success_at,
                last_failure_at=f.last_failure_at,
                last_error=f.last_error,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
        )
    return response


@router.post("/feeds", response_model=FeedResponse, status_code=status.HTTP_201_CREATED)
async def create_feed(
    payload: FeedCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a new RSS/Atom feed to a source (Requires authentication).
    """
    service = SourceService(db)
    source = await service.get_source_by_id(payload.source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID {payload.source_id} not found.",
        )

    feed = await service.create_feed(payload)
    return FeedResponse(
        id=feed.id,
        source_id=feed.source_id,
        source_name=source.name,
        name=feed.name,
        feed_url=feed.feed_url,
        feed_type=feed.feed_type,
        language=feed.language,
        is_active=feed.is_active,
        default_topic_id=feed.default_topic_id,
        last_fetched_at=feed.last_fetched_at,
        last_success_at=feed.last_success_at,
        last_failure_at=feed.last_failure_at,
        last_error=feed.last_error,
        created_at=feed.created_at,
        updated_at=feed.updated_at,
    )


@router.post("/feeds/{feed_id}/test", response_model=FeedTestResponse)
async def test_feed_endpoint(
    feed_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Test fetching and parsing a feed without storing articles into the database.
    """
    source_service = SourceService(db)
    feed = await source_service.get_feed_by_id(feed_id)
    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feed with ID {feed_id} not found.",
        )

    ingestion_service = IngestionService(db)
    result = await ingestion_service.test_feed(feed.feed_url)
    return result


@router.post("/feeds/{feed_id}/ingest", response_model=IngestionSummary)
async def ingest_feed_endpoint(
    feed_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger ingestion for a specific feed (Requires authentication).
    """
    source_service = SourceService(db)
    feed = await source_service.get_feed_by_id(feed_id)
    if not feed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feed with ID {feed_id} not found.",
        )

    ingestion_service = IngestionService(db)
    result = await ingestion_service.ingest_feed(feed_id)
    return result


@router.post("/ingest", response_model=IngestionBatchResponse)
async def ingest_all_feeds_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger batch ingestion for all active news feeds (Requires authentication).
    """
    ingestion_service = IngestionService(db)
    result = await ingestion_service.ingest_all_active_feeds()
    return result


@router.get("/runs", response_model=List[IngestionRunResponse])
async def get_ingestion_runs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List recent ingestion runs with statuses and statistics.
    """
    stmt = (
        select(IngestionRun)
        .options(selectinload(IngestionRun.feed))
        .order_by(desc(IngestionRun.started_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    runs = list(result.scalars().all())

    response = []
    for r in runs:
        response.append(
            IngestionRunResponse(
                id=r.id,
                feed_id=r.feed_id,
                feed_name=r.feed.name if r.feed else None,
                started_at=r.started_at,
                finished_at=r.finished_at,
                status=r.status,
                articles_fetched=r.articles_fetched,
                articles_created=r.articles_created,
                duplicates_found=r.duplicates_found,
                errors_count=r.errors_count,
                error_message=r.error_message,
            )
        )
    return response


# ---------------------------------------------------------------------------
# Phase 5: Web Extraction & Scraping Endpoints
# ---------------------------------------------------------------------------

@router.post("/articles/{article_id}/extract", response_model=ExtractionResultResponse)
async def extract_single_article(
    article_id: uuid.UUID,
    force: bool = Query(default=False, description="Re-extract even if full text is available"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers web article extraction for a single article by ID.

    Fetches the article webpage, checks robots.txt and content policies,
    extracts metadata and cleaned article body, and updates the database.
    """
    service = ArticleExtractionService(db)
    result = await service.extract_article(article_id, force=force)
    return ExtractionResultResponse(
        article_id=result.article_id,
        status=result.status.value if hasattr(result.status, "value") else str(result.status),
        title=result.title,
        author=result.author,
        content_length=result.content_length,
        canonical_url=result.canonical_url,
        extraction_method=result.extraction_method,
        is_full_text_available=result.is_full_text_available,
        error=result.error,
    )


@router.post("/articles/extract-pending", response_model=ExtractPendingResponse)
async def extract_pending_articles_endpoint(
    limit: int = Query(default=20, ge=1, le=100, description="Max articles to extract"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch extracts pending RSS-discovered articles that do not have full text.
    """
    service = ArticleExtractionService(db)
    result = await service.extract_pending_articles(limit=limit)
    return ExtractPendingResponse(**result)


@router.get("/articles/{article_id}/extraction-status", response_model=ExtractionStatusDetailResponse)
async def get_article_extraction_status(
    article_id: uuid.UUID,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Internal/development endpoint to inspect extraction metadata for an article.
    """
    stmt = select(Article).where(Article.id == article_id)
    res = await db.execute(stmt)
    article = res.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    return ExtractionStatusDetailResponse(
        article_id=article.id,
        status=article.extraction_status or article.scrape_status or "NOT_ATTEMPTED",
        method=article.extraction_method,
        extracted_at=article.extracted_at or article.scraped_at,
        content_length=len(article.content or ""),
        canonical_url=article.canonical_url or article.source_url,
        is_full_text_available=article.is_full_text_available,
        error=article.extraction_error or article.scrape_error,
    )


@router.post("/articles/{article_id}/scrape", response_model=ScrapeArticleResponse)
async def scrape_single_article(
    article_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers web scraping for a single article by ID (ScraperService compatibility).
    """
    scraper_service = ScraperService(db)
    result = await scraper_service.scrape_article(article_id)
    return ScrapeArticleResponse(**result)


@router.post("/scrape/batch", response_model=ScrapeBatchResponse)
async def scrape_pending_articles_batch(
    limit: int = Query(default=50, ge=1, le=200, description="Max articles to scrape in this batch"),
    feed_id: Optional[uuid.UUID] = Query(default=None, description="Limit to a specific feed"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch-scrapes pending articles (ScraperService compatibility).
    """
    scraper_service = ScraperService(db)
    result = await scraper_service.scrape_pending_articles(limit=limit, feed_id=feed_id)

    coerced_results = [
        ScrapeArticleResponse(**r) for r in result.get("results", [])
    ]
    return ScrapeBatchResponse(
        total_articles=result["total_articles"],
        success=result["success"],
        failed=result["failed"],
        robots_blocked=result["robots_blocked"],
        validation_failed=result["validation_failed"],
        skipped=result["skipped"],
        results=coerced_results,
    )

