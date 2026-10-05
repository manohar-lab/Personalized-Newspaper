"""app.ai.classification module."""
from app.ai.classification.classifier import TopicClassifier, slugify_topic
from app.ai.classification.prompts import (
    ARTICLE_ANALYSIS_SYSTEM_PROMPT,
    build_article_analysis_user_prompt,
)
from app.ai.classification.schemas import (
    ArticleAnalysisOutput,
    ArticleType,
    EntityExtractionItem,
    EntityType,
    KeywordExtractionItem,
    PrimaryCategory,
    TopicExtractionItem,
)

__all__ = [
    "TopicClassifier",
    "slugify_topic",
    "ARTICLE_ANALYSIS_SYSTEM_PROMPT",
    "build_article_analysis_user_prompt",
    "ArticleAnalysisOutput",
    "PrimaryCategory",
    "ArticleType",
    "EntityType",
    "TopicExtractionItem",
    "EntityExtractionItem",
    "KeywordExtractionItem",
]
