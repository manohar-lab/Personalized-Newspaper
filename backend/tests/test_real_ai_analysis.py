"""test_real_ai_analysis.py — Phase 7 Real Article AI Analysis Integration Tests.

Validates the complete AI analysis pipeline with realistic articles, checking:
1. Category classification
2. Topic resolution with confidence
3. Entity extraction with confidence
4. Keyword extraction with weights
5. Summary generation
6. Importance score calculation
7. Language detection
8. Vector embedding generation
9. Database persistence & retrieval
"""
import uuid
import pytest
from app.ai.services.article_analysis_service import ArticleAnalysisService
from app.models.article import Article
from app.models.source import NewsSource
from app.models.topic import Topic


@pytest.mark.asyncio
async def test_real_article_ai_analysis_flow(db_session):
    """Run full analysis pipeline on a realistic article in the test database."""
    # 1. Create a sample realistic news article
    source = NewsSource(
        id=uuid.uuid4(),
        name="MIT Technology Review",
        slug=f"mit-tech-review-{uuid.uuid4().hex[:6]}",
        website_url="https://technologyreview.com",
    )
    db_session.add(source)
    await db_session.flush()

    article = Article(
        id=uuid.uuid4(),
        title="OpenAI and NVIDIA Announce Next-Gen AI Supercomputing Architecture",
        slug=f"openai-nvidia-supercomputing-{uuid.uuid4().hex[:8]}",
        description="OpenAI and NVIDIA collaborate on a transformative deep learning infrastructure featuring new GPU clusters.",
        content=(
            "San Francisco — OpenAI and NVIDIA today unveiled a joint engineering initiative to deploy next-generation "
            "AI supercomputing clusters powered by advanced semiconductor hardware. The new architecture is designed to accelerate "
            "large language model training and reasoning performance by 5x while reducing energy consumption by 30%. "
            "Jensen Huang, CEO of NVIDIA, joined OpenAI leadership to demonstrate the system at a developer summit in California. "
            "The companies confirmed that production deployment will commence across global datacenters later this year."
        ),
        source_id=source.id,
        source_name=source.name,
        source_url="https://technologyreview.com/2026/09/openai-nvidia-supercomputer",
        status="PUBLISHED",
        is_full_text_available=True,
    )
    db_session.add(article)
    await db_session.commit()

    # 2. Run ArticleAnalysisService
    service = ArticleAnalysisService(session=db_session)
    result = await service.analyze_article(article.id)

    # 3. Inspect results
    assert result["status"] == "SUCCESS"
    assert result["primary_category"] == "TECHNOLOGY"
    assert result["article_type"] in ("NEWS", "ANNOUNCEMENT")
    assert 0.5 <= result["importance_score"] <= 1.0
    assert result["language"] == "en"
    assert len(result["summary"]) > 20
    assert result["has_embedding"] is True

    # 4. Verify topics
    topic_names = [t["name"] for t in result["topics"]]
    assert len(topic_names) > 0
    assert any("Intelligence" in name or "Software" in name or "Technology" in name for name in topic_names)
    for t in result["topics"]:
        assert 0.0 <= t["confidence"] <= 1.0

    # 5. Verify entities
    entity_names = [e["name"] for e in result["entities"]]
    assert any("OpenAI" in name or "NVIDIA" in name for name in entity_names)

    # 6. Verify keywords
    keywords = [k["keyword"] for k in result["keywords"]]
    assert len(keywords) > 0
    for k in result["keywords"]:
        assert 0.0 <= k["weight"] <= 1.0

    # 7. Verify DB persistence
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    stmt = select(Article).options(selectinload(Article.analysis)).where(Article.id == article.id)
    art_res = await db_session.execute(stmt)
    loaded_art = art_res.scalar_one()

    assert loaded_art.analysis is not None
    assert loaded_art.analysis.analysis_status == "SUCCESS"
    assert loaded_art.analysis.primary_category == "TECHNOLOGY"
    assert loaded_art.primary_category == "TECHNOLOGY"
    assert loaded_art.analysis.embedding is not None
    assert len(loaded_art.analysis.embedding) == 64
