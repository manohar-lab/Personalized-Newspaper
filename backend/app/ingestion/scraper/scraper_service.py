"""
scraper_service.py — Phase 5 Web Article Scraper Service

Orchestrates the web scraping pipeline for articles that were ingested
via RSS but whose full text has not yet been extracted:

    Article (RSS only, is_full_text_available=False)
        ↓
    Article URL
        ↓
    WebFetcher (robots.txt check + HTML fetch)
        ↓
    ContentExtractor (JSON-LD / OG / readability)
        ↓
    ContentCleaner (sanitize + truncate)
        ↓
    ArticleValidator (quality gate)
        ↓
    Database update (content, reading_time, scrape_status, etc.)

Design principles:
- Scraping failure is NOT a fatal error; articles remain available via RSS.
- Each article's scrape_status is tracked in the database.
- The service can process a single article or a batch.
- Compatible with asyncio; each article is scraped sequentially to
  avoid hammering the same domain simultaneously.
"""

import logging
import sys
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Path gymnastics to import from scraper package at project root
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scraper.extractors.web_fetcher import WebFetcher, FetchResult, FetchError, RobotsError
from scraper.extractors.content_extractor import ContentExtractor
from scraper.processors.content_cleaner import ContentCleaner
from scraper.processors.article_validator import ArticleValidator

from app.models.article import Article
from app.ingestion.rss.normalizer import ArticleNormalizer

logger = logging.getLogger(__name__)


# Scrape status constants
SCRAPE_STATUS_PENDING = "PENDING"
SCRAPE_STATUS_SUCCESS = "SUCCESS"
SCRAPE_STATUS_FAILED = "FAILED"
SCRAPE_STATUS_ROBOTS_BLOCKED = "ROBOTS_BLOCKED"
SCRAPE_STATUS_VALIDATION_FAILED = "VALIDATION_FAILED"
SCRAPE_STATUS_SKIPPED = "SKIPPED"


class ScraperService:
    """
    Orchestrates the full scraping pipeline for RSS-only articles.

    Usage:
        service = ScraperService(session=db_session)
        result = await service.scrape_article(article_id)
    """

    def __init__(
        self,
        session: AsyncSession,
        fetcher: Optional[WebFetcher] = None,
        extractor: Optional[ContentExtractor] = None,
        cleaner: Optional[ContentCleaner] = None,
        validator: Optional[ArticleValidator] = None,
        min_word_count: int = 100,
    ):
        self.session = session
        self.fetcher = fetcher or WebFetcher()
        self.extractor = extractor or ContentExtractor()
        self.cleaner = cleaner or ContentCleaner()
        self.validator = validator or ArticleValidator(min_word_count=min_word_count)

    async def scrape_article(self, article_id: uuid.UUID) -> Dict[str, Any]:
        """
        Scrapes a single article by its ID.

        Returns a result dict with status, scrape_status, and any error message.
        """
        # 1. Load article
        stmt = select(Article).where(Article.id == article_id)
        result = await self.session.execute(stmt)
        article = result.scalar_one_or_none()

        if not article:
            return {
                "article_id": article_id,
                "scrape_status": SCRAPE_STATUS_FAILED,
                "success": False,
                "error": f"Article {article_id} not found",
            }

        # 2. Determine URL to scrape
        url = article.canonical_url or article.source_url
        if not url:
            article.scrape_status = SCRAPE_STATUS_SKIPPED
            article.scrape_error = "No URL available for scraping"
            article.scraped_at = datetime.now(timezone.utc)
            await self.session.commit()
            return {
                "article_id": article_id,
                "scrape_status": SCRAPE_STATUS_SKIPPED,
                "success": False,
                "error": "No URL available for scraping",
            }

        logger.info(f"Scraping article '{article.title}' from: {url}")

        try:
            # 3. Fetch HTML
            fetch_result: FetchResult = await self.fetcher.fetch(url)

            # 4. Extract content
            extracted = self.extractor.extract(fetch_result.html, url)

            if not extracted.success:
                article.scrape_status = SCRAPE_STATUS_FAILED
                article.scrape_error = extracted.error or "Extraction produced no content"
                article.scraped_at = datetime.now(timezone.utc)
                await self.session.commit()
                return {
                    "article_id": article_id,
                    "scrape_status": SCRAPE_STATUS_FAILED,
                    "success": False,
                    "error": article.scrape_error,
                }

            # 5. Clean content
            cleaned = self.cleaner.clean(extracted)

            # 6. Validate
            validation = self.validator.validate(cleaned)

            if not validation.valid:
                status = (
                    SCRAPE_STATUS_VALIDATION_FAILED
                    if not validation.is_paywall_detected
                    else SCRAPE_STATUS_VALIDATION_FAILED
                )
                article.scrape_status = status
                article.scrape_error = "; ".join(validation.reasons)
                article.scraped_at = datetime.now(timezone.utc)
                await self.session.commit()

                logger.info(
                    f"Article '{article.title}' validation failed: {validation.reasons}"
                )
                return {
                    "article_id": article_id,
                    "scrape_status": status,
                    "success": False,
                    "error": article.scrape_error,
                    "word_count": validation.word_count,
                    "is_paywall": validation.is_paywall_detected,
                }

            # 7. Persist extracted content
            now = datetime.now(timezone.utc)

            # Update content fields
            article.content = cleaned.body_text
            article.is_full_text_available = True
            article.scrape_status = SCRAPE_STATUS_SUCCESS
            article.scrape_error = None
            article.scraped_at = now

            # Enrich metadata from scraped content (only if not already set from RSS)
            if not article.author and cleaned.author:
                article.author = cleaned.author
            if not article.description and cleaned.description:
                article.description = cleaned.description
            if not article.image_url and cleaned.image_url:
                article.image_url = cleaned.image_url

            # Update reading time from actual word count
            if validation.word_count > 0:
                article.reading_time_minutes = max(1, round(validation.word_count / 200))

            # Language from page HTML (only if not set)
            if not article.language or article.language == "en":
                if cleaned.language:
                    lang = cleaned.language[:10]
                    article.language = lang

            article.updated_at = now

            await self.session.commit()

            logger.info(
                f"Successfully scraped article '{article.title}': "
                f"{validation.word_count} words, method={cleaned.extraction_method}"
            )

            return {
                "article_id": article_id,
                "scrape_status": SCRAPE_STATUS_SUCCESS,
                "success": True,
                "word_count": validation.word_count,
                "extraction_method": cleaned.extraction_method,
                "reading_time_minutes": article.reading_time_minutes,
            }

        except RobotsError as exc:
            logger.info(f"Robots.txt blocked scraping of '{article.title}': {exc}")
            article.scrape_status = SCRAPE_STATUS_ROBOTS_BLOCKED
            article.scrape_error = str(exc)
            article.scraped_at = datetime.now(timezone.utc)
            await self.session.commit()
            return {
                "article_id": article_id,
                "scrape_status": SCRAPE_STATUS_ROBOTS_BLOCKED,
                "success": False,
                "error": str(exc),
            }

        except FetchError as exc:
            logger.warning(f"Fetch error scraping '{article.title}': {exc}")
            article.scrape_status = SCRAPE_STATUS_FAILED
            article.scrape_error = str(exc)
            article.scraped_at = datetime.now(timezone.utc)
            await self.session.commit()
            return {
                "article_id": article_id,
                "scrape_status": SCRAPE_STATUS_FAILED,
                "success": False,
                "error": str(exc),
            }

        except Exception as exc:
            logger.error(f"Unexpected error scraping '{article.title}': {exc}")
            try:
                article.scrape_status = SCRAPE_STATUS_FAILED
                article.scrape_error = f"Unexpected: {exc}"
                article.scraped_at = datetime.now(timezone.utc)
                await self.session.commit()
            except Exception:
                await self.session.rollback()
            return {
                "article_id": article_id,
                "scrape_status": SCRAPE_STATUS_FAILED,
                "success": False,
                "error": str(exc),
            }

    async def scrape_pending_articles(
        self,
        limit: int = 50,
        feed_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Scrapes all articles with scrape_status=PENDING (or NULL) that have
        no full text yet.

        Args:
            limit: Maximum number of articles to process in one batch.
            feed_id: If provided, only process articles from this feed.

        Returns:
            Batch summary dict.
        """
        from sqlalchemy import or_, is_

        stmt = (
            select(Article)
            .where(Article.is_full_text_available == False)
            .where(
                or_(
                    Article.scrape_status == SCRAPE_STATUS_PENDING,
                    Article.scrape_status.is_(None),
                )
            )
            .where(Article.canonical_url.isnot(None))
            .order_by(Article.published_at.desc())
            .limit(limit)
        )

        if feed_id:
            stmt = stmt.where(Article.feed_id == feed_id)

        result = await self.session.execute(stmt)
        articles = list(result.scalars().all())

        total = len(articles)
        success_count = 0
        failed_count = 0
        robots_blocked = 0
        validation_failed = 0
        skipped = 0

        results: List[Dict[str, Any]] = []

        logger.info(f"Starting batch scrape for {total} pending articles.")

        for article in articles:
            scrape_result = await self.scrape_article(article.id)
            results.append(scrape_result)

            status = scrape_result.get("scrape_status", SCRAPE_STATUS_FAILED)
            if status == SCRAPE_STATUS_SUCCESS:
                success_count += 1
            elif status == SCRAPE_STATUS_ROBOTS_BLOCKED:
                robots_blocked += 1
            elif status == SCRAPE_STATUS_VALIDATION_FAILED:
                validation_failed += 1
            elif status == SCRAPE_STATUS_SKIPPED:
                skipped += 1
            else:
                failed_count += 1

        return {
            "total_articles": total,
            "success": success_count,
            "failed": failed_count,
            "robots_blocked": robots_blocked,
            "validation_failed": validation_failed,
            "skipped": skipped,
            "results": results,
        }
