"""extractor.py — Phase 20 Web Article Content Extractor Interface.

Dispatches extraction to registered source-specific extractors or GenericSourceExtractor.
"""
from typing import Optional

from app.extraction.models import ExtractedArticleData
from app.extraction.sources.generic import GenericSourceExtractor
from app.extraction.sources.registry import extractor_registry
from app.extraction.validator import ArticleContentValidator


class WebArticleExtractor:
    """Dispatches article extraction via registry routing."""

    def __init__(self, validator: Optional[ArticleContentValidator] = None):
        self.validator = validator or ArticleContentValidator()
        self.generic = GenericSourceExtractor(validator=self.validator)

    def extract(self, html: str, source_url: str) -> ExtractedArticleData:
        """Extract article data using appropriate registered source extractor."""
        extractor = extractor_registry.get_extractor(source_url)
        return extractor.extract(html, source_url)


# Backward compatibility alias
GenericArticleExtractor = GenericSourceExtractor
