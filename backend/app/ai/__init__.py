"""app.ai package — Phase 7 AI Article Understanding & Classification."""
from app.ai.base import ArticleAnalyzer, EmbeddingProvider
from app.ai.classification.classifier import TopicClassifier
from app.ai.classification.schemas import (
    ArticleAnalysisOutput,
    ArticleType,
    EntityExtractionItem,
    EntityType,
    KeywordExtractionItem,
    PrimaryCategory,
    TopicExtractionItem,
)
from app.ai.embeddings.embedder import EmbeddingService, build_semantic_text_payload
from app.ai.entities.extractor import EntityResolver
from app.ai.providers.factory import get_article_analyzer, get_embedding_provider
from app.ai.services.article_analysis_service import ArticleAnalysisService
from app.ai.summarization.summarizer import ArticleSummarizer

__all__ = [
    "ArticleAnalyzer",
    "EmbeddingProvider",
    "TopicClassifier",
    "EntityResolver",
    "EmbeddingService",
    "ArticleSummarizer",
    "ArticleAnalysisService",
    "get_article_analyzer",
    "get_embedding_provider",
    "build_semantic_text_payload",
    "ArticleAnalysisOutput",
    "PrimaryCategory",
    "ArticleType",
    "EntityType",
    "TopicExtractionItem",
    "EntityExtractionItem",
    "KeywordExtractionItem",
]
