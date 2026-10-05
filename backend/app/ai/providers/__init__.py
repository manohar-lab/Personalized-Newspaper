"""app.ai.providers module."""
from app.ai.providers.factory import get_article_analyzer, get_embedding_provider
from app.ai.providers.mock_provider import MockArticleAnalyzer, MockEmbeddingProvider
from app.ai.providers.openai_provider import OpenAIArticleAnalyzer, OpenAIEmbeddingProvider
from app.ai.providers.gemini_provider import GeminiArticleAnalyzer

__all__ = [
    "get_article_analyzer",
    "get_embedding_provider",
    "MockArticleAnalyzer",
    "MockEmbeddingProvider",
    "OpenAIArticleAnalyzer",
    "OpenAIEmbeddingProvider",
    "GeminiArticleAnalyzer",
]
