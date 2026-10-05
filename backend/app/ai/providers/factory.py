"""factory.py — Phase 7 AI Provider Factory.

Instantiates configured ArticleAnalyzer and EmbeddingProvider based on application settings.
"""
import logging
from typing import Optional

from app.ai.base import ArticleAnalyzer, EmbeddingProvider
from app.ai.providers.mock_provider import MockArticleAnalyzer, MockEmbeddingProvider
from app.ai.providers.openai_provider import OpenAIArticleAnalyzer, OpenAIEmbeddingProvider
from app.ai.providers.gemini_provider import GeminiArticleAnalyzer
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_article_analyzer(provider_override: Optional[str] = None) -> ArticleAnalyzer:
    """Factory function returning configured ArticleAnalyzer."""
    provider = (provider_override or settings.AI_PROVIDER or "mock").lower().strip()

    if provider == "openai" and settings.AI_API_KEY:
        return OpenAIArticleAnalyzer()
    elif provider == "gemini" and settings.AI_API_KEY:
        return GeminiArticleAnalyzer()
    elif provider == "mock":
        return MockArticleAnalyzer()
    else:
        # Fallback to Mock if API key is missing or unrecognized provider
        if provider != "mock":
            logger.warning(
                f"Configured AI_PROVIDER '{provider}' is missing API key. Falling back to MockArticleAnalyzer."
            )
        return MockArticleAnalyzer()


def get_embedding_provider(provider_override: Optional[str] = None) -> EmbeddingProvider:
    """Factory function returning configured EmbeddingProvider."""
    provider = (provider_override or settings.EMBEDDING_PROVIDER or "mock").lower().strip()

    if provider == "openai" and settings.AI_API_KEY:
        return OpenAIEmbeddingProvider()
    elif provider == "mock":
        return MockEmbeddingProvider()
    else:
        return MockEmbeddingProvider()
