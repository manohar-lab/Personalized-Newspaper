"""base.py — Phase 20 Base Source Extractor.

Abstract base class for all news extractors with common helper methods
for JSON-LD parsing, OpenGraph, language identification, and timezone normalization.
"""
from abc import ABC, abstractmethod
import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.extraction.models import ExtractedArticleData


class BaseSourceExtractor(ABC):
    """Abstract base class for domain-specific and generic extractors."""

    @abstractmethod
    def matches_domain(self, url: str) -> bool:
        """Check if this extractor handles the given URL/domain."""
        pass

    @abstractmethod
    def extract(self, html: str, source_url: str) -> ExtractedArticleData:
        """Extract structured article data from the given HTML content."""
        pass

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract normalized domain from URL."""
        try:
            parsed = urlparse(url.strip())
            netloc = (parsed.netloc or "").lower().split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception:
            return ""

    @staticmethod
    def ensure_utc(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
        """Convert a datetime object to UTC timezone-aware datetime."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
