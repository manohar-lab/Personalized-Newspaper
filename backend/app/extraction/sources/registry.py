"""registry.py — Phase 20 Source Extractor Registry.

Manages domain-to-extractor routing with automatic fallback to GenericSourceExtractor.
"""
from typing import Dict, List, Optional
from urllib.parse import urlparse

from app.extraction.sources.base import BaseSourceExtractor
from app.extraction.sources.generic import GenericSourceExtractor


class ExtractorRegistry:
    """Registry for domain-specific and general article extractors."""

    def __init__(self):
        self._domain_extractors: Dict[str, BaseSourceExtractor] = {}
        self._custom_extractors: List[BaseSourceExtractor] = []
        self._generic_extractor = GenericSourceExtractor()

    def register(self, domain: str, extractor: BaseSourceExtractor) -> None:
        """Register an extractor for a specific domain (e.g. 'bbc.com', 'reuters.com')."""
        clean_domain = domain.lower().strip()
        if clean_domain.startswith("www."):
            clean_domain = clean_domain[4:]
        self._domain_extractors[clean_domain] = extractor

    def register_custom(self, extractor: BaseSourceExtractor) -> None:
        """Register an extractor with custom predicate matching."""
        self._custom_extractors.append(extractor)

    def get_extractor(self, url: str) -> BaseSourceExtractor:
        """Retrieve the best matching extractor for the URL, or fallback to GenericSourceExtractor."""
        if not url:
            return self._generic_extractor

        try:
            parsed = urlparse(url.strip())
            netloc = (parsed.netloc or "").lower().split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]

            # 1. Exact domain match
            if netloc in self._domain_extractors:
                return self._domain_extractors[netloc]

            # 2. Suffix / Subdomain match (e.g. news.ycombinator.com matches ycombinator.com)
            for registered_domain, extractor in self._domain_extractors.items():
                if netloc.endswith(f".{registered_domain}"):
                    return extractor

            # 3. Custom predicate check
            for custom_extractor in self._custom_extractors:
                if custom_extractor.matches_domain(url):
                    return custom_extractor

        except Exception:
            pass

        return self._generic_extractor


# Global singleton registry
extractor_registry = ExtractorRegistry()
