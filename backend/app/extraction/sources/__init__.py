"""sources package — Phase 20 Source-Specific and Generic Article Extractors.
"""
from app.extraction.sources.base import BaseSourceExtractor
from app.extraction.sources.generic import GenericSourceExtractor
from app.extraction.sources.registry import ExtractorRegistry, extractor_registry

__all__ = [
    "BaseSourceExtractor",
    "GenericSourceExtractor",
    "ExtractorRegistry",
    "extractor_registry",
]
