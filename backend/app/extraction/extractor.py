"""extractor.py — Phase 5 Generic Web Article Content Extractor.

Combines Trafilatura, Schema.org/JSON-LD, OpenGraph, and fallback heuristics
to extract clean, structured article data with strict priority resolution.
"""
import hashlib
import logging
from datetime import datetime
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
from app.extraction.validator import ArticleContentValidator

logger = logging.getLogger(__name__)


class GenericArticleExtractor:
    """Generic multi-layer web article extractor."""

    def __init__(self, validator: Optional[ArticleContentValidator] = None):
        self.validator = validator or ArticleContentValidator()

    def extract(self, html: str, source_url: str) -> ExtractedArticleData:
        """Extract article data from HTML document."""
        if not html:
            return ExtractedArticleData(
                url=source_url,
                status=ExtractionStatus.FAILED,
                error_message="HTML content is empty",
            )

        # 1. Parse structured metadata (JSON-LD, OG, Twitter, canonical, paywall flags)
        meta = HTMLMetadataParser.parse(html, source_url)

        # Check for instant paywall flag from JSON-LD or CSS classes
        if meta.is_paywalled:
            return ExtractedArticleData(
                url=source_url,
                status=ExtractionStatus.PAYWALL,
                title=meta.title,
                author=meta.author,
                description=meta.description,
                publication_date=meta.publication_date,
                image_url=meta.image_url,
                canonical_url=meta.canonical_url or source_url,
                language=meta.language or "en",
                error_message=meta.paywall_indicator or "Paywall detected",
            )

        # 2. Extract article body and metadata using Trafilatura if available
        traf_title: Optional[str] = None
        traf_author: Optional[str] = None
        traf_body: Optional[str] = None
        traf_date: Optional[str] = None
        traf_image: Optional[str] = None

        if TRAFILATURA_AVAILABLE:
            try:
                # Extract structured text
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

                # Extract metadata via trafilatura
                traf_meta = trafilatura.extract_metadata(html, default_url=source_url)
                if traf_meta:
                    traf_title = traf_meta.title
                    traf_author = traf_meta.author
                    traf_date = traf_meta.date
                    traf_image = traf_meta.image
            except Exception as e:
                logger.debug(f"Trafilatura extraction encountered an error: {e}")

        # 3. Determine extraction method and body content (Priority order)
        body_content: Optional[str] = None
        method: ExtractionMethod = ExtractionMethod.FALLBACK

        if traf_body and len(traf_body.strip()) >= 100:
            body_content = traf_body
            method = ExtractionMethod.TRAFILATURA
        elif meta.article_body and len(meta.article_body.strip()) >= 100:
            body_content = ContentCleaner.clean_text_content(meta.article_body)
            method = ExtractionMethod.JSON_LD
        else:
            # Fallback extraction from HTML
            cleaned_html_text = ContentCleaner.clean_html(html)
            if cleaned_html_text and len(cleaned_html_text.strip()) >= 100:
                body_content = cleaned_html_text
                method = ExtractionMethod.FALLBACK

        # 4. Resolve TITLE (Priority: 1. Structured metadata, 2. Article extractor, 3. HTML title)
        resolved_title = meta.title or traf_title

        # 5. Resolve AUTHOR (Priority: 1. Structured metadata, 2. Extractor metadata)
        resolved_author = meta.author or traf_author

        # 6. Resolve PUBLICATION DATE (Priority: 1. JSON-LD datePublished, 2. Meta date, 3. Extractor)
        resolved_date = meta.publication_date
        if not resolved_date and traf_date:
            resolved_date = HTMLMetadataParser._parse_date(traf_date)

        # 7. Resolve IMAGE (Priority: 1. Structured/OG metadata, 2. Extractor image)
        resolved_image = meta.image_url or traf_image

        # 8. Resolve CANONICAL URL
        canonical_url = meta.canonical_url or source_url

        # 9. Build intermediate article object
        article_data = ExtractedArticleData(
            url=source_url,
            method=method,
            title=resolved_title,
            author=resolved_author,
            description=meta.description,
            content=body_content,
            publication_date=resolved_date,
            image_url=resolved_image,
            canonical_url=canonical_url,
            language=meta.language or "en",
        )

        # 10. Validate extracted article
        is_valid, status, reason = self.validator.validate(article_data)
        article_data.status = status

        if not is_valid:
            article_data.error_message = reason
            # If invalid, discard raw body content for safety unless it's a paywall/partial
            if status != ExtractionStatus.PAYWALL:
                article_data.content = None
            return article_data

        # 11. Calculate content hash, length, reading time
        if article_data.content:
            article_data.content_length = len(article_data.content)
            article_data.content_hash = hashlib.sha256(article_data.content.encode("utf-8")).hexdigest()
            word_count = len(article_data.content.split())
            article_data.reading_time_minutes = max(1, round(word_count / 200))

        return article_data
