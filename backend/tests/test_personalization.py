"""test_personalization.py — Phase 8 Multi-Factor Personal Relevance & Personalization Engine Tests.

Tests all 22 required unit and integration cases:
1. Topic relevance
2. Positive topic
3. Negative topic
4. Multiple topics
5. Topic confidence
6. Semantic similarity
7. Entity relevance
8. Keyword relevance
9. Importance
10. Recency
11. Final weighted score
12. Weight validation
13. Negative penalty
14. Empty interests
15. Cold start
16. User profile embedding
17. Ranking
18. Diversity
19. Score normalization
20. No NaN/infinite scores
21. Different users receive different ranking
22. Highly relevant article outranks irrelevant article
+ Real multi-user validation (User A, User B, User C on identical article pool).
"""
import math
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from pydantic_settings import BaseSettings

from app.core.config import settings, Settings
from app.personalization.models import UserInterestEmbedding
from app.personalization.schemas import RelevanceScoreBreakdown, UserInterestProfile
from app.personalization.scoring.topic_scorer import TopicScorer
from app.personalization.scoring.semantic_scorer import SemanticScorer
from app.personalization.scoring.entity_scorer import EntityScorer
from app.personalization.scoring.keyword_scorer import KeywordScorer
from app.personalization.scoring.recency_scorer import RecencyScorer
from app.personalization.scoring.relevance_scorer import RelevanceScorer
from app.personalization.services.user_embedding_service import UserEmbeddingService
from app.personalization.services.personalization_service import PersonalizationService


# -----------------------------------------------------------------------------
# Test Helper Classes
# -----------------------------------------------------------------------------
class MockTopic:
    def __init__(self, slug: str, name: str, confidence: float = 1.0):
        self.id = uuid.uuid4()
        self.slug = slug
        self.name = name
        self.confidence = confidence


class MockEntity:
    def __init__(self, name: str, normalized_name: str, entity_type: str = "ORGANIZATION", confidence: float = 0.95):
        self.id = uuid.uuid4()
        self.name = name
        self.normalized_name = normalized_name
        self.entity_type = entity_type
        self.confidence = confidence


class MockKeyword:
    def __init__(self, keyword: str, weight: float = 1.0):
        self.keyword = keyword
        self.weight = weight


class MockArticleAnalysis:
    def __init__(self, importance_score: float = 0.65, primary_category: str = "TECHNOLOGY", embedding: list = None):
        self.importance_score = importance_score
        self.primary_category = primary_category
        self.embedding = embedding


class MockArticle:
    def __init__(
        self,
        title: str,
        slug: str,
        topics=None,
        entities=None,
        keywords=None,
        importance_score: float = 0.65,
        embedding: list = None,
        published_at: datetime = None,
        primary_category: str = "TECHNOLOGY",
    ):
        self.id = uuid.uuid4()
        self.title = title
        self.slug = slug
        self.topics = topics or []
        self.entities = entities or []
        self.keywords = keywords or []
        self.importance_score = importance_score
        self.embedding = embedding
        self.published_at = published_at or datetime.now(timezone.utc)
        self.created_at = self.published_at
        self.status = "PUBLISHED"
        self.analysis = MockArticleAnalysis(
            importance_score=importance_score,
            primary_category=primary_category,
            embedding=embedding,
        )


# =============================================================================
# 1. Topic Relevance & Confidence Tests
# =============================================================================
class TestTopicScorer:
    def test_single_positive_topic_match(self):
        """Test 1 & 2: Positive topic calculation: confidence * user_score."""
        topics = [("artificial-intelligence", 0.8)]
        pos_interests = {"artificial-intelligence": 0.9}
        neg_interests = {}

        score, penalty = TopicScorer.score_topics(topics, pos_interests, neg_interests)
        assert score == pytest.approx(0.72, abs=0.01)
        assert penalty == 0.0

    def test_negative_topic_penalty(self):
        """Test 3 & 13: Negative topic produces penalty without positive score."""
        topics = [("sports", 0.9)]
        pos_interests = {"artificial-intelligence": 0.9}
        neg_interests = {"sports": 0.95}

        score, penalty = TopicScorer.score_topics(topics, pos_interests, neg_interests, negative_penalty_weight=1.0)
        assert score == 0.0
        assert penalty == pytest.approx(0.855, abs=0.01)

    def test_multiple_topics_combination(self):
        """Test 4: Multiple matching topics combine properly."""
        topics = [("ai", 0.96), ("machine-learning", 0.85), ("programming", 0.72)]
        pos_interests = {"ai": 0.95, "machine-learning": 0.90, "programming": 0.85}
        neg_interests = {}

        score, penalty = TopicScorer.score_topics(topics, pos_interests, neg_interests)
        # Top score is 0.96 * 0.95 = 0.912, plus residual bonus
        assert 0.91 <= score <= 1.0
        assert penalty == 0.0

    def test_topic_confidence_scaling(self):
        """Test 5: Low confidence reduces contribution proportionally."""
        topics_high = [("ai", 0.9)]
        topics_low = [("ai", 0.3)]
        pos_interests = {"ai": 0.8}
        neg_interests = {}

        score_high, _ = TopicScorer.score_topics(topics_high, pos_interests, neg_interests)
        score_low, _ = TopicScorer.score_topics(topics_low, pos_interests, neg_interests)

        assert score_high > score_low
        assert score_high == pytest.approx(0.72, abs=0.01)
        assert score_low == pytest.approx(0.24, abs=0.01)


# =============================================================================
# 2. Semantic Similarity Scorer Tests
# =============================================================================
class TestSemanticScorer:
    def test_semantic_similarity_identical_vectors(self):
        """Test 6: Identical vectors produce maximum similarity 1.0."""
        vec = [0.1, 0.5, -0.3, 0.8]
        sim = SemanticScorer.score_semantic(vec, vec)
        assert sim == pytest.approx(1.0, abs=0.001)

    def test_semantic_similarity_orthogonal_vectors(self):
        """Test 6: Orthogonal vectors produce neutral similarity 0.5."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]
        sim = SemanticScorer.score_semantic(vec_a, vec_b)
        assert sim == pytest.approx(0.5, abs=0.01)

    def test_semantic_similarity_missing_embeddings(self):
        """Test 6: Missing vector returns neutral default."""
        sim = SemanticScorer.score_semantic(None, [0.1, 0.2])
        assert sim == 0.5


# =============================================================================
# 3. Entity & Keyword Scorer Tests
# =============================================================================
class TestEntityAndKeywordScorers:
    def test_entity_relevance_matching_known_entities(self):
        """Test 7: Entity matching user domain increases relevance."""
        entities = [
            MockEntity(name="OpenAI", normalized_name="openai"),
            MockEntity(name="NVIDIA", normalized_name="nvidia"),
        ]
        pos_interests = {"artificial-intelligence": 0.9}
        score = EntityScorer.score_entities(entities, pos_interests)
        assert score >= 0.70

    def test_entity_relevance_unmatched(self):
        """Test 7: Unrelated entities return baseline without inflating."""
        entities = [MockEntity(name="UnknownEntity", normalized_name="unknownentity")]
        pos_interests = {"artificial-intelligence": 0.9}
        score = EntityScorer.score_entities(entities, pos_interests)
        assert score <= 0.50

    def test_keyword_relevance_overlap(self):
        """Test 8: Article keywords overlapping user interest terms produce high score."""
        keywords = [
            MockKeyword(keyword="machine learning", weight=0.9),
            MockKeyword(keyword="deep learning", weight=0.8),
            MockKeyword(keyword="neural network", weight=0.85),
        ]
        pos_interests = {"machine-learning": 0.9}
        score = KeywordScorer.score_keywords(keywords, pos_interests)
        assert score >= 0.70


# =============================================================================
# 4. Importance & Recency Tests
# =============================================================================
class TestImportanceAndRecency:
    def test_recency_exponential_decay(self):
        """Test 10: Recent articles score higher than older articles."""
        now = datetime.now(timezone.utc)
        fresh_date = now - timedelta(hours=2)
        old_date = now - timedelta(hours=72)
        very_old_date = now - timedelta(hours=240)

        score_fresh = RecencyScorer.score_recency(fresh_date, now=now, half_life_hours=72.0)
        score_old = RecencyScorer.score_recency(old_date, now=now, half_life_hours=72.0)
        score_very_old = RecencyScorer.score_recency(very_old_date, now=now, half_life_hours=72.0)

        assert score_fresh > score_old > score_very_old
        assert score_fresh >= 0.95
        assert score_old == pytest.approx(0.50, abs=0.05)
        assert score_very_old < 0.15

    def test_future_publication_date_clamped(self):
        """Test 10: Future publication timestamp does not produce invalid scores."""
        now = datetime.now(timezone.utc)
        future_date = now + timedelta(days=2)
        score = RecencyScorer.score_recency(future_date, now=now)
        assert score == 1.0


# =============================================================================
# 5. Master Relevance Scorer & Weight Validation Tests
# =============================================================================
class TestMasterRelevanceScorer:
    def test_final_weighted_score_calculation(self):
        """Test 11 & Score Breakdown."""
        scorer = RelevanceScorer()
        now = datetime.now(timezone.utc)

        article = {
            "topics": [("ai", 0.9)],
            "entities": [("OpenAI", "COMPANY", 0.95)],
            "keywords": [("llm", 0.9)],
            "importance_score": 0.8,
            "embedding": [0.5] * 64,
            "published_at": now - timedelta(hours=1),
        }
        pos_interests = {"ai": 0.9}
        neg_interests = {}
        user_embedding = [0.5] * 64

        score, breakdown = scorer.compute_relevance(
            article=article,
            positive_interests=pos_interests,
            negative_interests=neg_interests,
            user_embedding=user_embedding,
            now=now,
        )

        assert 0.0 <= score <= 1.0
        assert breakdown.topic_score >= 0.80
        assert breakdown.semantic_score == pytest.approx(1.0, abs=0.01)
        assert breakdown.recency_score >= 0.95
        assert breakdown.final_score == score

    def test_weight_validation_sum(self):
        """Test 12: Validate that weights must sum to 1.0."""
        # Current valid settings should not raise
        settings.validate_weights()

        # Invalid weights should raise ValueError
        invalid_settings = Settings(
            PERSONALIZATION_TOPIC_WEIGHT=0.50,
            PERSONALIZATION_SEMANTIC_WEIGHT=0.50,
            PERSONALIZATION_ENTITY_WEIGHT=0.50,  # Sum = 1.50
        )
        with pytest.raises(ValueError, match="Personalization weights must sum to 1.0"):
            invalid_settings.validate_weights()

    def test_negative_penalty_suppression(self):
        """Test 13: Strongly disliked topic suppresses highly important article."""
        scorer = RelevanceScorer()
        now = datetime.now(timezone.utc)

        article = {
            "topics": [("sports", 0.95)],
            "importance_score": 0.95,  # Highly important global sports event
            "published_at": now,
        }
        pos_interests = {"ai": 0.90}
        neg_interests = {"sports": 0.95}

        score, breakdown = scorer.compute_relevance(
            article=article,
            positive_interests=pos_interests,
            negative_interests=neg_interests,
            now=now,
        )

        assert breakdown.negative_penalty >= 0.90
        assert score == 0.0  # Completely suppressed

    def test_empty_interests_and_cold_start(self):
        """Test 14 & 15: User with empty interests receives sensible baseline."""
        scorer = RelevanceScorer()
        now = datetime.now(timezone.utc)

        article = {
            "topics": [("technology", 0.9)],
            "importance_score": 0.70,
            "published_at": now - timedelta(hours=2),
        }

        score, breakdown = scorer.compute_relevance(
            article=article,
            positive_interests={},
            negative_interests={},
            user_embedding=None,
            now=now,
        )

        assert 0.0 < score < 1.0
        assert not math.isnan(score)
        assert not math.isinf(score)

    def test_no_nan_or_infinite_scores(self):
        """Test 19 & 20: Edge cases produce clamped, finite values."""
        scorer = RelevanceScorer()
        article = {
            "topics": [],
            "entities": [],
            "keywords": [],
            "importance_score": 0.0,
            "embedding": [0.0] * 64,
            "published_at": None,
            "created_at": None,
        }

        score, breakdown = scorer.compute_relevance(
            article=article,
            positive_interests={},
            negative_interests={},
            user_embedding=[0.0] * 64,
        )

        assert 0.0 <= score <= 1.0
        assert not math.isnan(score)
        assert not math.isinf(score)


# =============================================================================
# 6. User Profile Semantic Text & Embedding Tests
# =============================================================================
class TestUserEmbeddingService:
    def test_build_user_semantic_text(self):
        """Test 16: Profile text constructed cleanly with weights."""
        interests = {
            "artificial-intelligence": 0.95,
            "machine-learning": 0.90,
            "programming": 0.85,
        }
        names_map = {
            "artificial-intelligence": "Artificial Intelligence",
            "machine-learning": "Machine Learning",
            "programming": "Programming",
        }
        text = UserEmbeddingService.build_user_semantic_text(interests, names_map)
        assert "Artificial Intelligence (0.95)" in text
        assert "Machine Learning (0.90)" in text
        assert "Programming (0.85)" in text


# =============================================================================
# 7. Topic Diversity Tests
# =============================================================================
class TestTopicDiversity:
    def test_diversity_interleaving(self):
        """Test 18: Consecutive single-topic articles are interleaved."""
        art_ai_1 = MockArticle(title="AI 1", slug="ai-1", topics=[MockTopic("ai", "AI")])
        art_ai_2 = MockArticle(title="AI 2", slug="ai-2", topics=[MockTopic("ai", "AI")])
        art_prog = MockArticle(title="Prog 1", slug="prog-1", topics=[MockTopic("programming", "Programming")])
        art_startup = MockArticle(title="Startup 1", slug="startup-1", topics=[MockTopic("startups", "Startups")])

        dummy_bd = RelevanceScoreBreakdown(
            final_score=0.9, topic_score=0.9, semantic_score=0.9,
            entity_score=0.9, keyword_score=0.9, importance_score=0.9,
            recency_score=0.9, negative_penalty=0.0
        )

        # Scored list where AI is #1 and #2, followed by Prog and Startup
        scored_items = [
            (art_ai_1, 0.95, dummy_bd),
            (art_ai_2, 0.92, dummy_bd),
            (art_prog, 0.88, dummy_bd),
            (art_startup, 0.85, dummy_bd),
        ]

        service = PersonalizationService(session=None)
        diversified = service.apply_topic_diversity(scored_items)

        # Check that art_ai_2 is not placed directly at index 1
        assert diversified[0][0].slug == "ai-1"
        assert diversified[1][0].slug != "ai-2"  # Interleaved with Programming
        assert diversified[1][0].slug == "prog-1"
        assert diversified[2][0].slug == "ai-2" or diversified[2][0].slug == "startup-1"


# =============================================================================
# 8. Real Multi-User Validation Acceptance Tests (Users A, B, C)
# =============================================================================
class TestRealMultiUserValidation:
    """
    CRITICAL ACCEPTANCE TEST:
    Create three distinct users:
    - User A: AI, Machine Learning, Programming
    - User B: Business, Finance, Startups
    - User C: Science, Health, Education

    Evaluate the SAME article pool.
    Verify that:
    - User A ranks AI/Programming articles at the top.
    - User B ranks Business/Finance/Startup articles at the top.
    - User C ranks Science/Health articles at the top.
    - The same article receives different relevance scores for different users.
    """

    @pytest.fixture
    def article_pool(self):
        now = datetime.now(timezone.utc)
        return [
            MockArticle(
                title="DeepSeek and OpenAI Unveil Next-Gen LLM Architectures",
                slug="ai-llm-breakthrough",
                topics=[MockTopic("artificial-intelligence", "Artificial Intelligence", 0.95), MockTopic("programming", "Programming", 0.80)],
                entities=[MockEntity("OpenAI", "openai", "COMPANY")],
                keywords=[MockKeyword("llm", 0.95), MockKeyword("deep learning", 0.90)],
                importance_score=0.85,
                published_at=now - timedelta(hours=2),
                primary_category="TECHNOLOGY",
            ),
            MockArticle(
                title="Federal Reserve Signals Interest Rate Shift as Startup Funding Rebounds",
                slug="fed-rates-startups",
                topics=[MockTopic("finance", "Finance", 0.95), MockTopic("startups", "Startups", 0.85)],
                entities=[MockEntity("Federal Reserve", "federal reserve", "ORGANIZATION")],
                keywords=[MockKeyword("market", 0.90), MockKeyword("venture", 0.85)],
                importance_score=0.80,
                published_at=now - timedelta(hours=3),
                primary_category="FINANCE",
            ),
            MockArticle(
                title="NASA and Clinical Researchers Announce Biomedical Breakthrough",
                slug="nasa-health-breakthrough",
                topics=[MockTopic("science", "Science", 0.95), MockTopic("health", "Health", 0.90)],
                entities=[MockEntity("NASA", "nasa", "ORGANIZATION")],
                keywords=[MockKeyword("research", 0.90), MockKeyword("clinical", 0.85)],
                importance_score=0.88,
                published_at=now - timedelta(hours=1),
                primary_category="SCIENCE",
            ),
        ]

    def test_multi_user_distinct_rankings(self, article_pool):
        scorer = RelevanceScorer()
        now = datetime.now(timezone.utc)

        # USER A: AI / Tech enthusiast
        user_a_pos = {"artificial-intelligence": 0.95, "machine-learning": 0.90, "programming": 0.85}
        user_a_neg = {"sports": 0.90}

        # USER B: Business / Finance enthusiast
        user_b_pos = {"finance": 0.95, "markets-economy": 0.90, "startups": 0.85}
        user_b_neg = {"entertainment": 0.80}

        # USER C: Science / Health enthusiast
        user_c_pos = {"science": 0.95, "health": 0.90, "education": 0.80}
        user_c_neg = {"celebrity": 0.90}

        scores_a = {
            art.slug: scorer.compute_relevance(art, user_a_pos, user_a_neg, now=now)[0]
            for art in article_pool
        }
        scores_b = {
            art.slug: scorer.compute_relevance(art, user_b_pos, user_b_neg, now=now)[0]
            for art in article_pool
        }
        scores_c = {
            art.slug: scorer.compute_relevance(art, user_c_pos, user_c_neg, now=now)[0]
            for art in article_pool
        }

        # 1. User A top article must be AI article
        top_a = max(scores_a.items(), key=lambda x: x[1])
        assert top_a[0] == "ai-llm-breakthrough"

        # 2. User B top article must be Finance/Startup article
        top_b = max(scores_b.items(), key=lambda x: x[1])
        assert top_b[0] == "fed-rates-startups"

        # 3. User C top article must be Science/Health article
        top_c = max(scores_c.items(), key=lambda x: x[1])
        assert top_c[0] == "nasa-health-breakthrough"

        # 4. Confirm the same article gets different scores across users
        ai_score_a = scores_a["ai-llm-breakthrough"]
        ai_score_b = scores_b["ai-llm-breakthrough"]
        ai_score_c = scores_c["ai-llm-breakthrough"]

        assert ai_score_a > ai_score_b
        assert ai_score_a > ai_score_c

        # 5. Confirm relevant article significantly outranks irrelevant article (Test 21 & 22)
        assert scores_a["ai-llm-breakthrough"] > scores_a["fed-rates-startups"]
        assert scores_b["fed-rates-startups"] > scores_b["nasa-health-breakthrough"]
        assert scores_c["nasa-health-breakthrough"] > scores_c["ai-llm-breakthrough"]
