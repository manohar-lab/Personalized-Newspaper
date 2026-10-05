"""app.extraction module — Phase 5 Web Article Extraction & Scraping."""
from app.extraction.cleaner import ContentCleaner
from app.extraction.extractor import GenericArticleExtractor
from app.extraction.fetcher import FetchError, SSRFValidationError, WebPageFetcher
from app.extraction.models import (
    ExtractedArticleData,
    ExtractedMetadata,
    ExtractionMethod,
    ExtractionResult,
    ExtractionStatus,
    RobotsAccess,
)
from app.extraction.parser import HTMLMetadataParser
from app.extraction.robots import RobotsChecker
from app.extraction.validator import ArticleContentValidator

__all__ = [
    "WebPageFetcher",
    "RobotsChecker",
    "HTMLMetadataParser",
    "GenericArticleExtractor",
    "ContentCleaner",
    "ArticleContentValidator",
    "ExtractionStatus",
    "ExtractionMethod",
    "RobotsAccess",
    "ExtractedMetadata",
    "ExtractedArticleData",
    "ExtractionResult",
    "FetchError",
    "SSRFValidationError",
]
