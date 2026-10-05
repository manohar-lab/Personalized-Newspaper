"""article_extraction_service.py — Phase 5 Article Extraction Service.

Orchestrates the safe extraction of web articles discovered via RSS feeds.
Handles robots.txt checking, SSRF protection, multi-engine extraction,
per-domain rate limiting, concurrency management, and database persistence.
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.extraction.cleaner import ContentCleaner
from app.extraction.extractor import GenericArticleExtractor
from app.extraction.fetcher import FetchError, SSRFValidationError, WebPageFetcher
from app.extraction.models import (
    ExtractionMethod,
    ExtractionResult,
    ExtractionStatus,
    RobotsAccess,
)
from app.extraction.robots import RobotsChecker
from app.extraction.validator import ArticleContentValidator
from app.models.article import Article

logger = logging.getLogger(__name__)


class ArticleExtractionService:
    """Service to orchestrate extraction for individual articles or batches."""

    def __init__(
        self,
        session: AsyncSession,
        fetcher: Optional[WebPageFetcher] = None,
        robots_checker: Optional[RobotsChecker] = None,
        extractor: Optional[GenericArticleExtractor] = None,
        validator: Optional[ArticleContentValidator] = None,
    ):
        self.session = session
        self.fetcher = fetcher or WebPageFetcher()
        self.robots_checker = robots_checker or RobotsChecker()
        self.validator = validator or ArticleContentValidator()
        self.extractor = extractor or GenericArticleExtractor(validator=self.validator)

        # Per-domain rate limiting state: domain -> last_request_timestamp
        self._domain_last_request: Dict[str, float] = {}
        self._rate_limit_lock = asyncio.Lock()

    def _get_domain(self, url: str) -> str:
        """Get lowercase netloc from URL."""
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    async def _enforce_rate_limit(self, domain: str) -> None:
        """Ensure MIN_REQUEST_DELAY_SECONDS elapsed since last request to domain."""
        if not domain:
            return

        min_delay = getattr(settings, "MIN_REQUEST_DELAY_SECONDS", 1.0)
        async with self._rate_limit_lock:
            now = time.time()
            last_time = self._domain_last_request.get(domain, 0.0)
            elapsed = now - last_time
            if elapsed < min_delay:
                sleep_time = min_delay - elapsed
                await asyncio.sleep(sleep_time)
            self._domain_last_request[domain] = time.time()

    async def extract_article(self, article_id: uuid.UUID, force: bool = False) -> ExtractionResult:
        """Extract full web content for a single article.
        
        Args:
            article_id: UUID of article to extract.
            force: If True, re-extract even if full text is already present.
            
        Returns:
            ExtractionResult dataclass
        """
        # 1. Load article from DB
        stmt = select(Article).where(Article.id == article_id)
        res = await self.session.execute(stmt)
        article = res.scalar_one_or_none()

        if not article:
            return ExtractionResult(
                article_id=article_id,
                status=ExtractionStatus.FAILED,
                error="Article not found",
            )

        # 2. Check if extraction is needed
        if article.is_full_text_available and not force:
            return ExtractionResult(
                article_id=article.id,
                status=ExtractionStatus.SUCCESS,
                title=article.title,
                author=article.author,
                content_length=len(article.content or ""),
                canonical_url=article.canonical_url or article.source_url,
                extraction_method=article.extraction_method or "ALREADY_EXTRACTED",
                is_full_text_available=True,
            )

        target_url = article.source_url or article.canonical_url
        if not target_url:
            article.extraction_status = ExtractionStatus.FAILED.value
            article.scrape_status = "FAILED"
            article.extraction_error = "Article has no source URL"
            article.scrape_error = "Article has no source URL"
            article.extracted_at = datetime.now(timezone.utc)
            article.scraped_at = datetime.now(timezone.utc)
            await self.session.commit()
            return ExtractionResult(
                article_id=article.id,
                status=ExtractionStatus.FAILED,
                error="Article has no source URL",
            )

        # 3. Validate URL for SSRF safety before attempting connection
        is_safe, ssrf_reason = WebPageFetcher.is_ssrf_safe_url(target_url)
        if not is_safe:
            article.extraction_status = ExtractionStatus.FAILED.value
            article.scrape_status = "FAILED"
            article.extraction_error = f"Security error: {ssrf_reason}"
            article.scrape_error = f"Security error: {ssrf_reason}"
            article.extracted_at = datetime.now(timezone.utc)
            article.scraped_at = datetime.now(timezone.utc)
            await self.session.commit()
            return ExtractionResult(
                article_id=article.id,
                status=ExtractionStatus.FAILED,
                error=f"Security rejection: {ssrf_reason}",
            )

        # 4. Robots.txt check
        robots_result = await self.robots_checker.check_access(target_url)
        if robots_result == RobotsAccess.DISALLOWED:
            article.extraction_status = ExtractionStatus.ROBOTS_BLOCKED.value
            article.scrape_status = "ROBOTS_BLOCKED"
            article.extraction_error = "Extraction disallowed by publisher robots.txt"
            article.scrape_error = "Extraction disallowed by publisher robots.txt"
            article.extracted_at = datetime.now(timezone.utc)
            article.scraped_at = datetime.now(timezone.utc)
            await self.session.commit()
            return ExtractionResult(
                article_id=article.id,
                status=ExtractionStatus.ROBOTS_BLOCKED,
                error="Extraction disallowed by publisher robots.txt",
                canonical_url=article.canonical_url or target_url,
                is_full_text_available=False,
            )

        # 5. Enforce per-domain rate limit
        domain = self._get_domain(target_url)
        await self._enforce_rate_limit(domain)

        # 6. Fetch webpage HTML
        now_utc = datetime.now(timezone.utc)
        try:
            html, final_url, status_code = await self.fetcher.fetch(target_url)
        except SSRFValidationError as e:
            article.extraction_status = ExtractionStatus.FAILED.value
            article.scrape_status = "FAILED"
            article.extraction_error = f"SSRF security violation: {e}"
            article.scrape_error = str(e)
            article.extracted_at = now_utc
            article.scraped_at = now_utc
            await self.session.commit()
            return ExtractionResult(
                article_id=article.id,
                status=ExtractionStatus.FAILED,
                error=str(e),
                is_full_text_available=False,
            )
        except FetchError as e:
            error_status = ExtractionStatus.ACCESS_DENIED if e.status_code in (401, 403) else ExtractionStatus.FAILED
            article.extraction_status = error_status.value
            article.scrape_status = "FAILED"
            article.extraction_error = str(e)
            article.scrape_error = str(e)
            article.extracted_at = now_utc
            article.scraped_at = now_utc
            await self.session.commit()
            return ExtractionResult(
                article_id=article.id,
                status=error_status,
                error=str(e),
                is_full_text_available=False,
            )
        except Exception as e:
            article.extraction_status = ExtractionStatus.FAILED.value
            article.scrape_status = "FAILED"
            article.extraction_error = f"Unexpected fetch error: {e}"
            article.scrape_error = str(e)
            article.extracted_at = now_utc
            article.scraped_at = now_utc
            await self.session.commit()
            return ExtractionResult(
                article_id=article.id,
                status=ExtractionStatus.FAILED,
                error=str(e),
                is_full_text_available=False,
            )

        # 7. Extract article data and validate
        extracted_data = self.extractor.extract(html, final_url or target_url)

        if extracted_data.status == ExtractionStatus.PAYWALL:
            # Paywall detected: Do not overwrite existing content, mark status as PAYWALL
            article.extraction_status = ExtractionStatus.PAYWALL.value
            article.scrape_status = "FAILED"
            article.extraction_error = extracted_data.error_message or "Publisher requires subscription"
            article.scrape_error = article.extraction_error
            article.extracted_at = now_utc
            article.scraped_at = now_utc
            await self.session.commit()
            return ExtractionResult(
                article_id=article.id,
                status=ExtractionStatus.PAYWALL,
                title=article.title,
                author=article.author,
                canonical_url=extracted_data.canonical_url or target_url,
                error="Publisher requires subscription on its website",
                is_full_text_available=False,
            )

        if extracted_data.status != ExtractionStatus.SUCCESS or not extracted_data.content:
            # Failed or unsupported extraction: Preserve existing RSS metadata
            status_val = extracted_data.status.value if isinstance(extracted_data.status, ExtractionStatus) else "FAILED"
            article.extraction_status = status_val
            article.scrape_status = "FAILED"
            article.extraction_error = extracted_data.error_message or "Could not extract usable article content"
            article.scrape_error = article.extraction_error
            article.extracted_at = now_utc
            article.scraped_at = now_utc
            await self.session.commit()
            return ExtractionResult(
                article_id=article.id,
                status=extracted_data.status,
                title=article.title,
                author=article.author,
                canonical_url=extracted_data.canonical_url or target_url,
                error=extracted_data.error_message or "Extraction unsuccessful",
                is_full_text_available=False,
            )

        # 8. Successful extraction — Update article entity
        article.content = extracted_data.content
        article.is_full_text_available = True
        article.extraction_status = ExtractionStatus.SUCCESS.value
        article.scrape_status = "SUCCESS"
        article.extraction_method = extracted_data.method.value if extracted_data.method else "TRAFILATURA"
        article.extracted_at = now_utc
        article.scraped_at = now_utc
        article.extraction_error = None
        article.scrape_error = None
        article.content_hash = extracted_data.content_hash
        article.reading_time_minutes = extracted_data.reading_time_minutes or article.reading_time_minutes

        if extracted_data.canonical_url and not article.canonical_url:
            article.canonical_url = extracted_data.canonical_url

        # Enrich author / image if missing
        if extracted_data.author and (not article.author or article.author == "Unknown"):
            article.author = extracted_data.author
        if extracted_data.image_url and not article.image_url:
            article.image_url = extracted_data.image_url
        if extracted_data.publication_date and not article.published_at:
            article.published_at = extracted_data.publication_date

        await self.session.commit()

        return ExtractionResult(
            article_id=article.id,
            status=ExtractionStatus.SUCCESS,
            title=article.title,
            author=article.author,
            content_length=len(extracted_data.content),
            canonical_url=article.canonical_url or target_url,
            extraction_method=article.extraction_method,
            is_full_text_available=True,
        )

    async def extract_pending_articles(
        self,
        limit: int = 20,
        concurrency: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Batch extract articles that have not yet been extracted (or are pending).
        
        Args:
            limit: Maximum number of articles to extract in this batch.
            concurrency: Max concurrent worker tasks (default settings.EXTRACTION_CONCURRENCY).
        """
        max_concurrency = concurrency or getattr(settings, "EXTRACTION_CONCURRENCY", 3)
        sem = asyncio.Semaphore(max_concurrency)

        # Find candidate articles
        stmt = (
            select(Article.id)
            .where(
                and_(
                    Article.is_full_text_available.is_(False),
                    or_(
                        Article.extraction_status.is_(None),
                        Article.extraction_status == ExtractionStatus.NOT_ATTEMPTED.value,
                        Article.extraction_status == ExtractionStatus.PENDING.value,
                        Article.scrape_status.is_(None),
                        Article.scrape_status == "PENDING",
                    ),
                )
            )
            .order_by(Article.published_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        article_ids = list(res.scalars().all())

        if not article_ids:
            return {
                "total_articles": 0,
                "successful": 0,
                "failed": 0,
                "robots_blocked": 0,
                "paywalled": 0,
                "results": [],
            }

        # Mark selected articles as PENDING
        for aid in article_ids:
            art_res = await self.session.execute(select(Article).where(Article.id == aid))
            art = art_res.scalar_one_or_none()
            if art:
                art.extraction_status = ExtractionStatus.PENDING.value
                art.scrape_status = "PENDING"
        await self.session.commit()

        results: List[Dict[str, Any]] = []
        counts = {
            "SUCCESS": 0,
            "FAILED": 0,
            "ROBOTS_BLOCKED": 0,
            "PAYWALL": 0,
            "ACCESS_DENIED": 0,
            "UNSUPPORTED": 0,
        }

        async def _worker(aid: uuid.UUID) -> None:
            async with sem:
                try:
                    result = await self.extract_article(aid)
                    status_name = result.status.value if isinstance(result.status, ExtractionStatus) else str(result.status)
                    if status_name in counts:
                        counts[status_name] += 1
                    else:
                        counts["FAILED"] += 1

                    results.append({
                        "article_id": str(result.article_id),
                        "status": status_name,
                        "title": result.title,
                        "author": result.author,
                        "content_length": result.content_length,
                        "canonical_url": result.canonical_url,
                        "extraction_method": result.extraction_method,
                        "is_full_text_available": result.is_full_text_available,
                        "error": result.error,
                    })
                except Exception as exc:
                    logger.error(f"Error extracting article {aid}: {exc}")
                    counts["FAILED"] += 1
                    results.append({
                        "article_id": str(aid),
                        "status": ExtractionStatus.FAILED.value,
                        "error": str(exc),
                        "is_full_text_available": False,
                    })

        tasks = [_worker(aid) for aid in article_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "total_articles": len(article_ids),
            "successful": counts["SUCCESS"],
            "failed": counts["FAILED"],
            "robots_blocked": counts["ROBOTS_BLOCKED"],
            "paywalled": counts["PAYWALL"],
            "access_denied": counts["ACCESS_DENIED"],
            "unsupported": counts["UNSUPPORTED"],
            "results": results,
        }
