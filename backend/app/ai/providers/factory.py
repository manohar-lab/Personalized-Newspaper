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
    api_key = settings.get_ai_api_key(provider)

    if provider == "openai" and api_key:
        return OpenAIArticleAnalyzer(api_key=api_key)
    elif provider == "gemini" and api_key:
        return GeminiArticleAnalyzer(api_key=api_key)
    elif provider == "mock":
        return MockArticleAnalyzer()
    else:
        # Fallback to Mock if API key is missing or unrecognized provider
        if provider != "mock":
            if provider == "gemini":
                logger.warning(
                    "Configured AI_PROVIDER 'gemini' is missing API key (expected GEMINI_API_KEY, GOOGLE_API_KEY, or AI_API_KEY). "
                    "Falling back to MockArticleAnalyzer."
                )
            else:
                logger.warning(
                    f"Configured AI_PROVIDER '{provider}' is missing API key. Falling back to MockArticleAnalyzer."
                )
        return MockArticleAnalyzer()


def get_embedding_provider(provider_override: Optional[str] = None) -> EmbeddingProvider:
    """Factory function returning configured EmbeddingProvider."""
    provider = (provider_override or settings.EMBEDDING_PROVIDER or "mock").lower().strip()
    api_key = settings.get_ai_api_key(provider)

    if provider == "openai" and api_key:
        return OpenAIEmbeddingProvider(api_key=api_key)
    elif provider == "mock":
        return MockEmbeddingProvider()
    else:
        return MockEmbeddingProvider()
