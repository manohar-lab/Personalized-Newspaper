"""robust_ingestion_service.py — Phase 20 Robust News Ingestion & Real Web Intelligence Engine.

Orchestrates the entire ingestion lifecycle:
SOURCE -> FEED DISCOVERY -> RSS/ATOM (Conditional Requests / ETag / 304) ->
URL VALIDATION -> ROBOTS CHECK -> SAFE FETCH -> CONTENT EXTRACTION ->
QUALITY VALIDATION -> CLEANING -> CANONICALIZATION -> DEDUPLICATION ->
ARTICLE STORAGE -> STORY MATCHING & AI NOTIFICATIONS.
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

import feedparser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.extraction.cleaner import ContentCleaner
from app.extraction.fetcher import FetchError, SSRFValidationError, WebPageFetcher
from app.extraction.models import ExtractionStatus, RobotsAccess
from app.extraction.robots import RobotsChecker
from app.extraction.sources.registry import extractor_registry
from app.extraction.url_normalizer import URLNormalizer
from app.models.article import Article
from app.models.feed import NewsFeed
from app.models.ingestion_job import IngestionJob
from app.models.source import NewsSource
from app.services.article_versioning_service import ArticleVersioningService
from app.services.syndication_service import SyndicationDetector

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RobustIngestionService:
    """Enterprise-grade news ingestion service with worker pool, conditional requests, and error isolation."""

    def __init__(
        self,
        session: AsyncSession,
        max_concurrent_fetches: int = 5,
        fetcher: Optional[WebPageFetcher] = None,
        robots_checker: Optional[RobotsChecker] = None,
    ):
        self.session = session
        self.max_concurrent_fetches = max_concurrent_fetches
        self.fetcher = fetcher or WebPageFetcher()
        self.robots_checker = robots_checker or RobotsChecker()
        self.versioning_service = ArticleVersioningService(session)

    # -------------------------------------------------------------------------
    # SOURCE HEALTH & STALENESS
    # -------------------------------------------------------------------------
    @staticmethod
    def calculate_source_health(
        success_count: int,
        failure_count: int,
        last_success_at: Optional[datetime],
        robots_status: str = "ALLOWED",
    ) -> Tuple[str, float]:
        """Compute health status (HEALTHY, DEGRADED, FAILING, BLOCKED, STALE) and quality score.
        
        Returns:
            (health_status_str, health_score_float)
        """
        if robots_status == "BLOCKED":
            return "BLOCKED", 0.0

        total_runs = success_count + failure_count
        if total_runs == 0:
            return "HEALTHY", 0.80

        success_rate = success_count / total_runs

        # Staleness check: if no success in past 7 days and has had runs
        now = utc_now()
        is_stale = False
        if last_success_at:
            if now - last_success_at > timedelta(days=7):
                is_stale = True
        elif total_runs > 3 and success_count == 0:
            is_stale = True

        if is_stale:
            return "DEGRADED", round(max(0.1, success_rate * 0.5), 2)

        if success_rate >= 0.80:
            return "HEALTHY", round(success_rate, 2)
        elif success_rate >= 0.40:
            return "DEGRADED", round(success_rate, 2)
        else:
            return "FAILING", round(success_rate, 2)

    # -------------------------------------------------------------------------
    # FEED INGESTION
    # -------------------------------------------------------------------------
    async def ingest_feed(
        self,
        feed: NewsFeed,
        job_id: Optional[uuid.UUID] = None,
        force_fetch: bool = False,
    ) -> Dict[str, Any]:
        """Ingest a single feed with conditional requests (ETag / Last-Modified) and fault isolation."""
        now = utc_now()
        feed_url = feed.feed_url
        logger.info(f"Starting ingestion for feed '{feed.name}' ({feed_url})")

        stats = {
            "feed_id": str(feed.id),
            "feed_name": feed.name,
            "status": "SUCCESS",
            "items_processed": 0,
            "items_created": 0,
            "items_updated": 0,
            "items_skipped_304": False,
            "duplicates": 0,
            "errors": 0,
            "error_message": None,
        }

        # 1. Robots check on feed URL
        robots_access = await self.robots_checker.check_access(feed_url)
        if robots_access == RobotsAccess.DISALLOWED:
            feed.health_status = "BLOCKED"
            feed.last_failure_at = now
            feed.failure_count += 1
            feed.last_error = "Robots.txt blocks feed URL"
            stats["status"] = "BLOCKED"
            stats["error_message"] = "Robots.txt blocks feed URL"
            return stats

        # 2. Fetch feed content with conditional requests (ETag & Last-Modified)
        etag_to_send = None if force_fetch else feed.etag
        last_modified_to_send = None if force_fetch else feed.last_modified

        try:
            fetch_res = await self.fetcher.fetch_safe(
                feed_url,
                etag=etag_to_send,
                last_modified=last_modified_to_send,
            )
        except Exception as e:
            logger.warning(f"Fetch failed for feed '{feed.name}': {e}")
            feed.last_failure_at = now
            feed.failure_count += 1
            feed.last_error = str(e)
            feed.http_status = getattr(e, "status_code", 500) or 500
            feed.health_status = "FAILING" if feed.failure_count >= 3 else "DEGRADED"
            stats["status"] = "FAILED"
            stats["errors"] = 1
            stats["error_message"] = str(e)
            return stats

        # 3. Handle HTTP 304 Not Modified
        feed.last_fetched_at = now
        feed.http_status = fetch_res.status_code

        if fetch_res.is_not_modified or fetch_res.status_code == 304:
            logger.info(f"Feed '{feed.name}' returned 304 Not Modified. Skipping item processing.")
            feed.last_success_at = now
            feed.success_count += 1
            stats["items_skipped_304"] = True
            stats["status"] = "NOT_MODIFIED"
            return stats

        # 4. Save updated ETag and Last-Modified headers
        if fetch_res.etag:
            feed.etag = fetch_res.etag
        if fetch_res.last_modified:
            feed.last_modified = fetch_res.last_modified

        # 5. Parse RSS/Atom markup
        raw_xml = fetch_res.html
        parsed = feedparser.parse(raw_xml)

        if parsed.bozo and not parsed.entries:
            feed.last_failure_at = now
            feed.failure_count += 1
            feed.last_error = f"Malformed feed XML: {parsed.bozo_exception}"
            stats["status"] = "FAILED"
            stats["errors"] = 1
            stats["error_message"] = f"Malformed XML: {parsed.bozo_exception}"
            return stats

        feed.last_success_at = now
        feed.success_count += 1
        feed.health_status = "HEALTHY"
        feed.last_error = None

        # 6. Process Feed Items
        entries = parsed.entries or []
        stats["items_processed"] = len(entries)

        for entry in entries:
            try:
                created, updated, is_dup = await self._process_feed_entry(feed, entry)
                if created:
                    stats["items_created"] += 1
                elif updated:
                    stats["items_updated"] += 1
                elif is_dup:
                    stats["duplicates"] += 1
            except Exception as item_err:
                logger.debug(f"Error processing entry in feed {feed.name}: {item_err}")
                stats["errors"] += 1

        return stats

    async def _process_feed_entry(
        self, feed: NewsFeed, entry: Any
    ) -> Tuple[bool, bool, bool]:
        """Process a single RSS/Atom entry with normalization, deduplication, and versioning.
        
        Returns:
            (is_created, is_updated, is_duplicate)
        """
        raw_title = getattr(entry, "title", "") or ""
        raw_link = getattr(entry, "link", "") or ""
        raw_desc = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        raw_author = getattr(entry, "author", None)

        if not raw_link:
            return False, False, False

        # Normalize URL & strip tracking parameters
        canonical_url = URLNormalizer.normalize_url(raw_link)
        normalized_title = ContentCleaner.clean_text_content(raw_title)

        if not canonical_url or not normalized_title:
            return False, False, False

        # Check SSRF safety
        is_safe, _ = WebPageFetcher.is_ssrf_safe_url(canonical_url)
        if not is_safe:
            return False, False, False

        # Parse publication date
        published_at = utc_now()
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                published_at = utc_now()
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                published_at = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                published_at = utc_now()

        # Check existing article by canonical URL
        stmt = select(Article).where(
            (Article.canonical_url == canonical_url) | (Article.source_url == raw_link)
        )
        result = await self.session.execute(stmt)
        existing_article = result.scalars().first()

        clean_desc = ContentCleaner.clean_html(raw_desc) if raw_desc else None

        if existing_article:
            # Check for meaningful content updates
            if clean_desc and existing_article.content:
                was_updated = await self.versioning_service.check_and_apply_update(
                    existing_article,
                    new_content=clean_desc,
                    new_title=normalized_title,
                )
                if was_updated:
                    return False, True, False
            return False, False, True

        # Compute content fingerprint
        content_hash = hashlib.sha256(
            (canonical_url + normalized_title + (clean_desc or "")[:500]).encode("utf-8")
        ).hexdigest()

        # Create slug
        base_slug = normalized_title.lower()[:80].replace(" ", "-")
        clean_slug = "".join(c for c in base_slug if c.isalnum() or c == "-") + f"-{uuid.uuid4().hex[:6]}"

        article = Article(
            title=normalized_title,
            slug=clean_slug,
            description=clean_desc,
            content=clean_desc,
            source_id=feed.source_id,
            feed_id=feed.id,
            source_name=feed.source.name if feed.source else None,
            source_url=raw_link,
            canonical_url=canonical_url,
            ingestion_method="RSS",
            author=raw_author,
            published_at=published_at,
            content_hash=content_hash,
            language=feed.language or "en",
            status="PUBLISHED",
            scrape_status="PENDING",
            extraction_status="PENDING",
            is_full_text_available=bool(clean_desc and len(clean_desc) > 300),
        )
        self.session.add(article)
        return True, False, False

    # -------------------------------------------------------------------------
    # ARTICLE EXTRACTION RUNNER
    # -------------------------------------------------------------------------
    async def extract_article_content(self, article: Article) -> Article:
        """Safely fetch, extract, validate, and update an article's full content."""
        target_url = article.canonical_url or article.source_url
        if not target_url:
            article.extraction_status = "FAILED"
            article.extraction_error = "No URL available for extraction"
            return article

        # 1. Robots.txt check
        robots_access = await self.robots_checker.check_access(target_url)
        if robots_access == RobotsAccess.DISALLOWED:
            article.extraction_status = "ROBOTS_BLOCKED"
            article.scrape_status = "ROBOTS_BLOCKED"
            article.extraction_error = "Robots.txt blocks article crawling"
            return article

        # 2. Safe Fetch
        try:
            fetch_res = await self.fetcher.fetch_safe(target_url)
        except SSRFValidationError as ssrf_err:
            article.extraction_status = "FAILED"
            article.scrape_status = "FAILED"
            article.extraction_error = f"SSRF security violation: {ssrf_err}"
            return article
        except FetchError as fetch_err:
            status_code = fetch_err.status_code or 500
            if status_code in (401, 403):
                article.extraction_status = "ACCESS_DENIED"
            elif status_code == 404:
                article.extraction_status = "FAILED"
            elif status_code == 429:
                article.extraction_status = "FAILED"
            else:
                article.extraction_status = "FAILED"
            article.scrape_status = "FAILED"
            article.extraction_error = str(fetch_err)
            return article
        except Exception as exc:
            article.extraction_status = "FAILED"
            article.scrape_status = "FAILED"
            article.extraction_error = f"Fetch error: {exc}"
            return article

        # 3. Extract & Validate with Source Extractor
        extractor = extractor_registry.get_extractor(target_url)
        extracted = extractor.extract(fetch_res.html, fetch_res.final_url or target_url)

        article.extraction_status = extracted.status.value
        article.scrape_status = "SUCCESS" if extracted.status == ExtractionStatus.SUCCESS else "FAILED"
        article.scraped_at = utc_now()
        article.extracted_at = utc_now()

        if extracted.status == ExtractionStatus.SUCCESS and extracted.content:
            article.title = extracted.title or article.title
            article.content = extracted.content
            article.content_hash = extracted.content_hash
            article.author = extracted.author or article.author
            article.image_url = extracted.image_url or article.image_url
            article.reading_time_minutes = extracted.reading_time_minutes
            article.is_full_text_available = True
            article.extraction_method = extracted.method.value if extracted.method else "GENERIC"
            article.canonical_url = extracted.canonical_url or article.canonical_url
            if extracted.publication_date:
                article.published_at = extracted.publication_date
            if extracted.language:
                article.language = extracted.language
        else:
            article.extraction_error = extracted.error_message
            if extracted.status == ExtractionStatus.PAYWALL:
                # Retain whatever description / snippet was extracted
                if extracted.description and not article.description:
                    article.description = extracted.description

        return article

    # -------------------------------------------------------------------------
    # BULK INGESTION RUNNER WITH BACKPRESSURE
    # -------------------------------------------------------------------------
    async def run_ingestion_pipeline(self, max_feeds: int = 20) -> IngestionJob:
        """Run robust ingestion round with concurrency control and job tracking."""
        job = IngestionJob(
            job_type="FEED_INGESTION",
            status="RUNNING",
            started_at=utc_now(),
        )
        self.session.add(job)
        await self.session.flush()

        # Query active feeds
        stmt = select(NewsFeed).where(NewsFeed.is_active.is_(True)).limit(max_feeds)
        res = await self.session.execute(stmt)
        feeds = list(res.scalars().all())

        total_processed = 0
        total_created = 0
        total_updated = 0
        total_failed = 0

        # Concurrency semaphore
        semaphore = asyncio.Semaphore(self.max_concurrent_fetches)

        async def _bounded_feed_run(f: NewsFeed) -> Dict[str, Any]:
            async with semaphore:
                return await self.ingest_feed(f, job_id=job.id)

        results = await asyncio.gather(
            *[_bounded_feed_run(f) for f in feeds], return_exceptions=True
        )

        for r in results:
            if isinstance(r, dict):
                total_processed += r.get("items_processed", 0)
                total_created += r.get("items_created", 0)
                total_updated += r.get("items_updated", 0)
                if r.get("status") == "FAILED":
                    total_failed += 1
            else:
                total_failed += 1

        job.status = "COMPLETED" if total_failed == 0 else ("PARTIAL" if total_created > 0 else "FAILED")
        job.completed_at = utc_now()
        job.items_processed = total_processed
        job.items_created = total_created
        job.items_updated = total_updated
        job.items_failed = total_failed

        await self.session.commit()
        return job
