"""generic.py — Phase 20 Generic Source Extractor.

Performs robust multi-layered extraction across JSON-LD, OpenGraph,
Semantic HTML, and heuristic fallback methods.
"""
import hashlib
import logging
from typing import Optional

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

from app.extraction.cleaner import ContentCleaner
from app.extraction.models import (
    ExtractedArticleData,
    ExtractionMethod,
    ExtractionStatus,
)
from app.extraction.parser import HTMLMetadataParser
from app.extraction.quality import ArticleQualityScorer
from app.extraction.sources.base import BaseSourceExtractor
from app.extraction.url_normalizer import URLNormalizer
from app.extraction.validator import ArticleContentValidator

logger = logging.getLogger(__name__)


class GenericSourceExtractor(BaseSourceExtractor):
    """Universal web article extractor implementing priority-based extraction."""

    def __init__(self, validator: Optional[ArticleContentValidator] = None):
        self.validator = validator or ArticleContentValidator()

    def matches_domain(self, url: str) -> bool:
        return True  # Fallback matches all domains

    def extract(self, html: str, source_url: str) -> ExtractedArticleData:
        """Extract article data from HTML document."""
        if not html:
            return ExtractedArticleData(
                url=source_url,
                status=ExtractionStatus.FAILED,
                error_message="HTML content is empty",
            )

        # 1. Parse structured metadata (JSON-LD, OpenGraph, Twitter, canonical)
        meta = HTMLMetadataParser.parse(html, source_url)

        # 2. Check for instant paywall flag from JSON-LD / HTML classes
        if meta.is_paywalled:
            canonical = URLNormalizer.resolve_canonical(source_url, meta.canonical_url)
            return ExtractedArticleData(
                url=source_url,
                status=ExtractionStatus.PAYWALL,
                title=meta.title,
                headline=meta.title,
                author=meta.author,
                description=meta.description,
                publication_date=self.ensure_utc(meta.publication_date),
                updated_date=self.ensure_utc(meta.updated_date),
                image_url=meta.image_url,
                canonical_url=canonical,
                language=meta.language or "en",
                error_message=meta.paywall_indicator or "Paywall detected",
            )

        # 3. Extract article body via Trafilatura if available
        traf_title: Optional[str] = None
        traf_author: Optional[str] = None
        traf_body: Optional[str] = None
        traf_date: Optional[str] = None
        traf_image: Optional[str] = None

        if TRAFILATURA_AVAILABLE:
            try:
                traf_extracted = trafilatura.extract(
                    html,
                    url=source_url,
                    include_comments=False,
                    include_tables=True,
                    include_links=False,
                    output_format="txt",
                    favor_precision=True,
                )
                if traf_extracted:
                    traf_body = ContentCleaner.clean_text_content(traf_extracted)

                traf_meta = trafilatura.extract_metadata(html, default_url=source_url)
                if traf_meta:
                    traf_title = traf_meta.title
                    traf_author = traf_meta.author
                    traf_date = traf_meta.date
                    traf_image = traf_meta.image
            except Exception as e:
                logger.debug(f"Trafilatura extraction encountered an error: {e}")

        # 4. Resolve Body Content & Method (Priority: 1. Trafilatura, 2. JSON-LD articleBody, 3. Cleaned HTML)
        body_content: Optional[str] = None
        method: ExtractionMethod = ExtractionMethod.FALLBACK

        if traf_body and len(traf_body.strip()) >= 100:
            body_content = traf_body
            method = ExtractionMethod.TRAFILATURA
        elif meta.article_body and len(meta.article_body.strip()) >= 100:
            body_content = ContentCleaner.clean_text_content(meta.article_body)
            method = ExtractionMethod.JSON_LD
        else:
            cleaned_html_text = ContentCleaner.clean_html(html)
            if cleaned_html_text and len(cleaned_html_text.strip()) >= 100:
                body_content = cleaned_html_text
                method = ExtractionMethod.FALLBACK

        # 5. Resolve Title / Headline
        resolved_title = meta.title or traf_title

        # 6. Resolve Author
        resolved_author = meta.author or traf_author

        # 7. Resolve Dates (normalized to UTC)
        resolved_date = self.ensure_utc(meta.publication_date)
        if not resolved_date and traf_date:
            resolved_date = self.ensure_utc(HTMLMetadataParser._parse_date(traf_date))

        resolved_updated = self.ensure_utc(meta.updated_date)

        # 8. Resolve Image
        resolved_image = meta.image_url or traf_image

        # 9. Canonical URL resolution with tracking parameter stripping
        canonical_url = URLNormalizer.resolve_canonical(source_url, meta.canonical_url)

        # 10. Build intermediate article object
        article_data = ExtractedArticleData(
            url=source_url,
            method=method,
            title=resolved_title,
            headline=resolved_title,
            author=resolved_author,
            description=meta.description,
            content=body_content,
            publication_date=resolved_date,
            updated_date=resolved_updated,
            image_url=resolved_image,
            canonical_url=canonical_url,
            language=meta.language or "en",
        )

        # 11. Validate extracted article & score quality
        is_valid, status, reason = self.validator.validate(article_data)
        article_data.status = status

        if not is_valid:
            article_data.error_message = reason
            if status != ExtractionStatus.PAYWALL:
                article_data.content = None
            return article_data

        # 12. Calculate content hash, length, reading time
        if article_data.content:
            article_data.content_length = len(article_data.content)
            article_data.content_hash = hashlib.sha256(
                article_data.content.encode("utf-8")
            ).hexdigest()
            word_count = len(article_data.content.split())
            article_data.reading_time_minutes = max(1, round(word_count / 200))

        # Evaluate quality score
        breakdown = ArticleQualityScorer.evaluate(article_data)
        article_data.quality_breakdown = breakdown
        article_data.quality_score = breakdown.overall_score

        return article_data
