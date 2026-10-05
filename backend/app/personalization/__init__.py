"""personalization module — Phase 8 Personal Relevance Scoring & Multi-Factor Engine."""
from app.personalization.models import UserInterestEmbedding
from app.personalization.schemas import (
    RelevanceScoreBreakdown,
    UserInterestProfile,
    ScoredArticle,
)
from app.personalization.scoring.relevance_scorer import RelevanceScorer
from app.personalization.scoring.topic_scorer import TopicScorer
from app.personalization.scoring.semantic_scorer import SemanticScorer
from app.personalization.scoring.entity_scorer import EntityScorer
from app.personalization.scoring.keyword_scorer import KeywordScorer
from app.personalization.scoring.recency_scorer import RecencyScorer
from app.personalization.services.user_embedding_service import UserEmbeddingService
from app.personalization.services.personalization_service import PersonalizationService

__all__ = [
    "UserInterestEmbedding",
    "RelevanceScoreBreakdown",
    "UserInterestProfile",
    "ScoredArticle",
    "RelevanceScorer",
    "TopicScorer",
    "SemanticScorer",
    "EntityScorer",
    "KeywordScorer",
    "RecencyScorer",
    "UserEmbeddingService",
    "PersonalizationService",
]
