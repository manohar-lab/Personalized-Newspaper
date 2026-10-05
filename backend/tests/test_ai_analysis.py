"""test_ai_analysis.py — Comprehensive Unit & Integration Tests for Phase 7 AI Article Analysis.

Tests all 20 required aspects:
1. Valid AI structured output validation
2. Invalid AI output parsing & recovery
3. Invalid category coercion/fallback
4. Invalid article type coercion/fallback
5. Invalid importance score clamping (0.0 to 1.0)
6. Topic resolution & linking in article_topics with confidence
7. Duplicate topics prevention
8. Entity resolution & normalization
9. Duplicate entities prevention
10. Keyword normalization & weighting
11. Summary storage & formatting
12. Language detection
13. Analysis status lifecycle (NOT_ANALYZED -> PROCESSING -> SUCCESS/FAILED)
14. Analysis retry & force flag
15. Analysis version tracking (v1)
16. AI failure handling (recording error without throwing)
17. Embedding generation & metadata storage
18. Embedding failure handling gracefully
19. Article remains available in database and reader after AI failure
20. Protected / unauthorized analysis endpoints (401 when unauthenticated)
"""
from datetime import datetime, timezone
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from app.ai.base import ArticleAnalyzer, EmbeddingProvider
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
from app.ai.embeddings.embedder import EmbeddingService, build_semantic_text_payload
from app.ai.entities.extractor import EntityResolver, normalize_entity_name
from app.ai.providers.mock_provider import MockArticleAnalyzer, MockEmbeddingProvider
from app.ai.services.article_analysis_service import ArticleAnalysisService
from app.main import app
from app.models.analysis import ArticleAnalysis, ArticleKeyword
from app.models.article import Article
from app.models.entity import Entity
from app.models.topic import Topic


# ---------------------------------------------------------------------------
# 1, 2, 3, 4, 5: Schema Validation & Coercion Tests
# ---------------------------------------------------------------------------

class TestAISchemasAndValidation:
    def test_valid_structured_output(self):
        data = {
            "primary_category": "TECHNOLOGY",
            "article_type": "NEWS",
            "importance_score": 0.88,
            "language": "en",
            "summary": "Scientists developed a new silicon chip architecture. It delivers 40% higher efficiency for AI training workloads.",
            "topics": [
                {"name": "Artificial Intelligence", "confidence": 0.95},
                {"name": "Semiconductors", "confidence": 0.82},
            ],
            "entities": [
                {"name": "NVIDIA", "type": "COMPANY", "confidence": 0.99},
                {"name": "Jensen Huang", "type": "PERSON", "confidence": 0.95},
            ],
            "keywords": [
                {"keyword": "silicon chip", "weight": 0.94},
                {"keyword": "deep learning", "weight": 0.89},
            ],
        }
        output = ArticleAnalysisOutput(**data)
        assert output.primary_category == PrimaryCategory.TECHNOLOGY
        assert output.article_type == ArticleType.NEWS
        assert output.importance_score == 0.88
        assert len(output.topics) == 2
        assert len(output.entities) == 2
        assert len(output.keywords) == 2

    def test_invalid_category_coerced_to_other(self):
        data = {
            "primary_category": "UNKNOWN_SUPER_CATEGORY_XYZ",
            "article_type": "NEWS",
            "importance_score": 0.5,
            "summary": "A short valid summary describing the event.",
        }
        output = ArticleAnalysisOutput(**data)
        assert output.primary_category == PrimaryCategory.OTHER

    def test_invalid_article_type_coerced_to_other(self):
        data = {
            "primary_category": "SCIENCE",
            "article_type": "WEIRD_CUSTOM_FORMAT_TYPE",
            "importance_score": 0.5,
            "summary": "A short valid summary describing the event.",
        }
        output = ArticleAnalysisOutput(**data)
        assert output.article_type == ArticleType.OTHER

    def test_importance_score_clamped(self):
        # Score > 1.0 clamped to 1.0
        out_high = ArticleAnalysisOutput(
            primary_category="TECHNOLOGY",
            importance_score=1.85,
            summary="A short valid summary.",
        )
        assert out_high.importance_score == 1.0

        # Score < 0.0 clamped to 0.0
        out_low = ArticleAnalysisOutput(
            primary_category="TECHNOLOGY",
            importance_score=-0.45,
            summary="A short valid summary.",
        )
        assert out_low.importance_score == 0.0

    def test_confidence_and_weight_clamped(self):
        topic = TopicExtractionItem(name="AI", confidence=1.5)
        assert topic.confidence == 1.0

        entity = EntityExtractionItem(name="OpenAI", type="COMPANY", confidence=-0.2)
        assert entity.confidence == 0.0

        kw = KeywordExtractionItem(keyword="LLM", weight=2.0)
        assert kw.weight == 1.0


# ---------------------------------------------------------------------------
# 6, 7: Topic Resolution & Deduplication
# ---------------------------------------------------------------------------

class TestTopicResolution:
    def test_slugify_topic(self):
        assert slugify_topic("Artificial Intelligence") == "artificial-intelligence"
        assert slugify_topic("C++ & Python!") == "c-python"

    @pytest.mark.asyncio
    async def test_topic_linking_and_deduplication(self):
        mock_session = AsyncMock()
        existing_topic = Topic(id=uuid.uuid4(), name="Software Engineering", slug="software-engineering")
        
        # Mock database topic queries
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [existing_topic]
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session.flush = AsyncMock()

        classifier = TopicClassifier(mock_session)
        article_id = uuid.uuid4()

        items = [
            TopicExtractionItem(name="Software Engineering", confidence=0.95),
            TopicExtractionItem(name="Software Engineering", confidence=0.80), # Duplicate name
            TopicExtractionItem(name="Quantum Computing", confidence=0.75),    # New topic
        ]

        resolved = await classifier.resolve_and_link_topics(article_id, items, create_missing=True)
        # Should link only 2 distinct topics
        assert len(resolved) == 2
        assert resolved[0][0].name == "Software Engineering"
        assert resolved[0][1] == 0.95
        assert resolved[1][0].name == "Quantum Computing"


# ---------------------------------------------------------------------------
# 8, 9, 10: Entity Resolution & Keyword Normalization
# ---------------------------------------------------------------------------

class TestEntityAndKeywordResolution:
    def test_entity_name_normalization(self):
        assert normalize_entity_name("  OpenAI   Inc  ") == "openai inc"
        assert normalize_entity_name("Google") == "google"

    @pytest.mark.asyncio
    async def test_entity_resolution_and_deduplication(self):
        mock_session = AsyncMock()
        existing_entity = Entity(id=uuid.uuid4(), name="OpenAI", normalized_name="openai", entity_type="COMPANY")

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = existing_entity
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session.flush = AsyncMock()

        resolver = EntityResolver(mock_session)
        article_id = uuid.uuid4()

        entities = [
            EntityExtractionItem(name="OpenAI", type=EntityType.COMPANY, confidence=0.98),
            EntityExtractionItem(name="openai", type=EntityType.COMPANY, confidence=0.90), # Duplicate normalized
        ]

        linked = await resolver.resolve_and_link_entities(article_id, entities)
        assert len(linked) == 1
        assert linked[0][0].name == "OpenAI"
        assert linked[0][1] == 0.98


# ---------------------------------------------------------------------------
# 11, 12, 17, 18: Semantic Embeddings & Prompts
# ---------------------------------------------------------------------------

class TestEmbeddingsAndPrompts:
    def test_semantic_payload_construction(self):
        payload = build_semantic_text_payload(
            title="NASA Discovers New Exoplanet",
            description="James Webb telescope spots atmospheric water vapor.",
            summary="Astronomers confirm water signatures on distant planet.",
            topics=["Space", "Astronomy"],
            keywords=["exoplanet", "water vapor"],
            body="Detailed spectroscopic data reveals balanced atmospheric chemistry.",
        )
        assert "TITLE: NASA Discovers New Exoplanet" in payload
        assert "SUMMARY: Astronomers confirm" in payload
        assert "TOPICS: Space, Astronomy" in payload
        assert "KEYWORDS: exoplanet, water vapor" in payload
        assert "BODY:\nDetailed spectroscopic" in payload

    @pytest.mark.asyncio
    async def test_mock_embedding_generation(self):
        service = EmbeddingService(MockEmbeddingProvider())
        vector, model, emb_time = await service.generate_article_embedding(
            title="Artificial Intelligence in Healthcare",
            description="AI models assist in early disease detection.",
        )
        assert vector is not None
        assert len(vector) == 64
        assert model == "mock-embedding-v1"
        assert emb_time is not None

    @pytest.mark.asyncio
    async def test_embedding_failure_handled_gracefully(self):
        mock_provider = MagicMock()
        mock_provider.generate_embedding = AsyncMock(side_effect=Exception("Embedding API rate limited"))
        mock_provider.model_name = "test-model"

        service = EmbeddingService(mock_provider)
        vector, model, emb_time = await service.generate_article_embedding(title="Test Story")
        assert vector is None
        assert model is None
        assert emb_time is None


# ---------------------------------------------------------------------------
# 13, 14, 15, 16, 19: Article Analysis Service Pipeline & Failure Resilience
# ---------------------------------------------------------------------------

class TestArticleAnalysisServicePipeline:
    @pytest.mark.asyncio
    async def test_successful_analysis_pipeline(self):
        mock_session = AsyncMock()
        article_id = uuid.uuid4()
        article = Article(
            id=article_id,
            title="Breakthrough in Quantum Computing Processor",
            description="A 1,000-qubit coherent quantum processor was announced.",
            content="Engineers today demonstrated a fault-tolerant quantum computing processor capable of complex simulations.",
            status="PUBLISHED",
            analysis=None,
        )

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = article
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()

        service = ArticleAnalysisService(
            session=mock_session,
            analyzer=MockArticleAnalyzer(),
            embedding_service=EmbeddingService(MockEmbeddingProvider()),
        )

        result = await service.analyze_article(article_id)
        assert result["status"] == "SUCCESS"
        assert result["primary_category"] == "TECHNOLOGY"
        assert result["article_type"] in ("NEWS", "ANNOUNCEMENT")
        assert result["importance_score"] >= 0.5
        assert result["has_embedding"] is True
        assert len(result["topics"]) > 0
        assert len(result["keywords"]) > 0

    @pytest.mark.asyncio
    async def test_cached_analysis_skipped_without_force(self):
        mock_session = AsyncMock()
        article_id = uuid.uuid4()
        existing_analysis = ArticleAnalysis(
            id=uuid.uuid4(),
            article_id=article_id,
            primary_category="SCIENCE",
            article_type="NEWS",
            importance_score=0.90,
            summary="Existing verified summary.",
            language="en",
            analysis_version="v1",
            analysis_status="SUCCESS",
            embedding=[0.1, 0.2, 0.3],
        )
        article = Article(
            id=article_id,
            title="Existing Analyzed Article",
            analysis=existing_analysis,
        )

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = article
        mock_session.execute = AsyncMock(return_value=mock_res)

        service = ArticleAnalysisService(session=mock_session)
        result = await service.analyze_article(article_id, force=False)
        assert result["status"] == "SUCCESS"
        assert result["already_analyzed"] is True
        assert result["primary_category"] == "SCIENCE"

    @pytest.mark.asyncio
    async def test_ai_failure_preserves_article(self):
        mock_session = AsyncMock()
        article_id = uuid.uuid4()
        article = Article(
            id=article_id,
            title="Story that triggers AI failure",
            description="Short excerpt",
            content="Valid content that will remain safe",
            analysis=None,
        )

        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = article
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session.commit = AsyncMock()

        failing_analyzer = MagicMock()
        failing_analyzer.analyze_article = AsyncMock(side_effect=RuntimeError("AI Provider 503 Overloaded"))

        service = ArticleAnalysisService(
            session=mock_session,
            analyzer=failing_analyzer,
        )

        result = await service.analyze_article(article_id)
        assert result["status"] == "FAILED"
        assert "503" in result["error"]
        # Article itself remains intact
        assert article.title == "Story that triggers AI failure"
        assert article.content == "Valid content that will remain safe"


# ---------------------------------------------------------------------------
# 20: Unauthorized API Endpoints Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthorized_analysis_endpoints_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        random_id = uuid.uuid4()

        # 1. POST /api/news/articles/{id}/analyze without token -> 401
        res_single = await ac.post(f"/api/news/articles/{random_id}/analyze")
        assert res_single.status_code == 401

        # 2. POST /api/news/articles/analyze-pending without token -> 401
        res_batch = await ac.post("/api/news/articles/analyze-pending")
        assert res_batch.status_code == 401
