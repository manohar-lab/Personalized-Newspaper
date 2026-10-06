"""recommendations package — Phase 14 Personalized News Discovery & Recommendation Engine."""
from app.recommendations.recommendation_service import RecommendationService
from app.recommendations.candidate_generator import CandidateGenerator
from app.recommendations.candidate_filters import CandidateFilters
from app.recommendations.scoring import RecommendationScorer
from app.recommendations.diversity import RecommendationDiversityEngine
from app.recommendations.explanations import ExplanationGenerator
from app.recommendations.models import UserRecommendation

__all__ = [
    "RecommendationService",
    "CandidateGenerator",
    "CandidateFilters",
    "RecommendationScorer",
    "RecommendationDiversityEngine",
    "ExplanationGenerator",
    "UserRecommendation",
]
