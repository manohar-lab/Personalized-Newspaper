"""test_search.py — Phase 11 Intelligent Personalized Search Engine Tests."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User
from app.models.topic import Topic
from app.models.entity import Entity
from app.models.interest import UserInterest
from app.models.source import NewsSource
from app.models.article import Article
from app.models.analysis import ArticleAnalysis, ArticleKeyword
from app.models.search import UserSearchHistory
from app.search.search_service import SearchService
from app.search.schemas import SearchFilterParams
from app.search.query_parser import QueryParser
from app.search.ranking import HybridSearchRanker


# -----------------------------------------------------------------------------
# Fixtures & Helpers
# -----------------------------------------------------------------------------
async def create_test_user(db: AsyncSession, prefix: str = "search_user") -> User:
    uid = uuid.uuid4().hex[:6]
    user = User(
        email=f"{prefix}_{uid}@example.com",
        password_hash="hashed_pw",
        full_name=f"Search User {uid}",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_test_topic(db: AsyncSession, name: str, slug: str) -> Topic:
    stmt = select(Topic).where(Topic.slug == slug)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return existing
    top = Topic(name=name, slug=slug)
    db.add(top)
    await db.commit()
    await db.refresh(top)
    return top


async def create_test_entity(db: AsyncSession, name: str, entity_type: str = "ORGANIZATION") -> Entity:
    norm = name.lower().strip()
    stmt = select(Entity).where(Entity.normalized_name == norm)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return existing
    ent = Entity(name=name, normalized_name=norm, entity_type=entity_type)
    db.add(ent)
    await db.commit()
    await db.refresh(ent)
    return ent


async def create_search_article(
    db: AsyncSession,
    title: str,
    category: str,
    topics: List[Topic],
    entities: Optional[List[Entity]] = None,
    keywords: Optional[List[str]] = None,
    source_name: str = "Reuters",
    content: Optional[str] = None,
    published_at: Optional[datetime] = None,
    embedding: Optional[List[float]] = None,
) -> Article:
    now = published_at or datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    art = Article(
        title=title,
        slug=f"search-slug-{uid}",
        canonical_url=f"https://news.example.com/{uid}",
        description=f"Detailed briefing and description for {title}.",
        content=content or f"Full validated article text covering {title} and its industry impact in detail.",
        status="PUBLISHED",
        published_at=now,
        source_name=source_name,
        is_full_text_available=True,
        reading_time_minutes=4,
    )
    art.topics = list(topics)
    if entities:
        art.entities = list(entities)

    db.add(art)
    await db.flush()

    # Add keywords
    if keywords:
        for kw in keywords:
            kw_obj = ArticleKeyword(article_id=art.id, keyword=kw.lower(), weight=1.0)
            db.add(kw_obj)

    # Add Analysis
    ana = ArticleAnalysis(
        article_id=art.id,
        primary_category=category,
        importance_score=0.85,
        summary=f"Key executive analytical summary on {title}.",
        embedding=embedding or [0.1] * 384,
        analysis_status="SUCCESS",
        analyzed_at=datetime.now(timezone.utc),
    )
    art.analysis = ana
    db.add(ana)
    await db.commit()
    await db.refresh(art)
    return art


# -----------------------------------------------------------------------------
# 1. Deterministic Query Parser Tests
# -----------------------------------------------------------------------------
def test_query_parser():
    # Test date detection
    parsed, d_from, d_to = QueryParser.parse_query("OpenAI announcements today")
    assert "OpenAI" in parsed.detected_entities
    assert parsed.date_range_detected == "today"
    assert d_from is not None
    assert "today" not in parsed.clean_keywords.lower()

    # Test topic detection
    parsed2, _, _ = QueryParser.parse_query("latest machine learning research")
    assert "Machine Learning" in parsed2.detected_topics
    assert "machine learning research" in parsed2.raw_query


# -----------------------------------------------------------------------------
# 2. Basic Keyword & Full-Text Search
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_full_text_and_keyword_search(db_session: AsyncSession):
    topic = await create_test_topic(db_session, "Technology", "tech-search-1")
    art = await create_search_article(
        db_session,
        title="Quantum Computing Breakthrough at MIT",
        category="TECHNOLOGY",
        topics=[topic],
        content="Scientists at MIT have developed a superconducting quantum chip.",
    )

    service = SearchService(db_session)
    res = await service.search(SearchFilterParams(q="Quantum Computing MIT"))

    assert res.total_results >= 1
    found = next((r for r in res.results if r.article_id == art.id), None)
    assert found is not None
    assert found.full_text_score > 0.0


# -----------------------------------------------------------------------------
# 3. Semantic Vector Search & Fallback
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_semantic_search_and_fallback(db_session: AsyncSession):
    from app.ai.embeddings.embedder import EmbeddingService
    topic = await create_test_topic(db_session, "Science", "science-search-1")
    # Embedding vector from the active embedding service provider
    emb = await EmbeddingService().provider.generate_embedding("Astrophysicists Discover Exoplanet in Habitable Zone")
    art = await create_search_article(
        db_session,
        title="Astrophysicists Discover Exoplanet in Habitable Zone",
        category="SCIENCE",
        topics=[topic],
        embedding=emb,
    )

    service = SearchService(db_session)
    res = await service.search(SearchFilterParams(q="Astrophysicists Discover Exoplanet in Habitable Zone"))
    assert res.total_results >= 1
    found = next((r for r in res.results if r.article_id == art.id), None)
    assert found is not None
    assert found.semantic_score > 0.0


# -----------------------------------------------------------------------------
# 4. Topic, Entity & Keyword Boost Matching
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_topic_and_entity_boost(db_session: AsyncSession):
    topic = await create_test_topic(db_session, "Machine Learning", "machine-learning-boost")
    ent = await create_test_entity(db_session, "OpenAI", "ORGANIZATION")

    art = await create_search_article(
        db_session,
        title="New Reasoning Models Released",
        category="TECHNOLOGY",
        topics=[topic],
        entities=[ent],
        keywords=["neural network", "transformer"],
    )

    service = SearchService(db_session)
    # Searching for "OpenAI machine learning"
    res = await service.search(SearchFilterParams(q="OpenAI machine learning"))
    found = next((r for r in res.results if r.article_id == art.id), None)
    assert found is not None
    assert found.search_score >= found.full_text_score
    assert found.match_explanation is not None


# -----------------------------------------------------------------------------
# 5. Personalized Search Ranking (User A vs User B)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_personalized_search_ranking(db_session: AsyncSession):
    # User A loves AI
    user_a = await create_test_user(db_session, "user_a")
    topic_ai = await create_test_topic(db_session, "Artificial Intelligence", "ai-user-a")
    db_session.add(UserInterest(user_id=user_a.id, topic_id=topic_ai.id, interest_score=1.0, preference_type="POSITIVE", source="EXPLICIT"))

    # User B loves Finance
    user_b = await create_test_user(db_session, "user_b")
    topic_fin = await create_test_topic(db_session, "Finance", "fin-user-b")
    db_session.add(UserInterest(user_id=user_b.id, topic_id=topic_fin.id, interest_score=1.0, preference_type="POSITIVE", source="EXPLICIT"))
    await db_session.commit()

    # Create two articles that both match "technology" query
    art_ai = await create_search_article(
        db_session,
        title="AI Software Platform Technology Update",
        category="TECHNOLOGY",
        topics=[topic_ai],
    )
    art_fin = await create_search_article(
        db_session,
        title="Fintech Technology Platform Update",
        category="BUSINESS",
        topics=[topic_fin],
    )

    service = SearchService(db_session)
    res_a = await service.search(SearchFilterParams(q="technology platform"), user_id=user_a.id)
    res_b = await service.search(SearchFilterParams(q="technology platform"), user_id=user_b.id)

    # For User A, AI article should rank higher
    idx_ai_a = next((i for i, r in enumerate(res_a.results) if r.article_id == art_ai.id), 99)
    idx_fin_a = next((i for i, r in enumerate(res_a.results) if r.article_id == art_fin.id), 99)
    assert idx_ai_a < idx_fin_a

    # For User B, Fintech article should rank higher
    idx_ai_b = next((i for i, r in enumerate(res_b.results) if r.article_id == art_ai.id), 99)
    idx_fin_b = next((i for i, r in enumerate(res_b.results) if r.article_id == art_fin.id), 99)
    assert idx_fin_b < idx_ai_b


# -----------------------------------------------------------------------------
# 6. Filters (Category, Source, Date Range, Language)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_filters(db_session: AsyncSession):
    topic = await create_test_topic(db_session, "World", "world-filter")
    now = datetime.now(timezone.utc)

    u_tag = uuid.uuid4().hex[:6]
    art_reuters = await create_search_article(
        db_session,
        title=f"UniqueTrade_{u_tag} Global Trade Summit Concludes",
        category="WORLD",
        topics=[topic],
        source_name="Reuters",
        published_at=now - timedelta(days=2),
    )
    art_bbc = await create_search_article(
        db_session,
        title=f"UniqueTrade_{u_tag} Global Environmental Forum Opens",
        category="SCIENCE",
        topics=[topic],
        source_name="BBC",
        published_at=now - timedelta(days=10),
    )

    service = SearchService(db_session)

    # Category filter
    res_cat = await service.search(
        SearchFilterParams(q=f"UniqueTrade_{u_tag}", category="WORLD", page_size=50)
    )
    assert any(r.article_id == art_reuters.id for r in res_cat.results)
    assert not any(r.article_id == art_bbc.id for r in res_cat.results)

    # Source filter
    res_src = await service.search(
        SearchFilterParams(q=f"UniqueTrade_{u_tag}", source="BBC", page_size=50)
    )
    assert any(r.article_id == art_bbc.id for r in res_src.results)
    assert not any(r.article_id == art_reuters.id for r in res_src.results)

    # Date filter (past 5 days)
    res_date = await service.search(
        SearchFilterParams(q=f"UniqueTrade_{u_tag}", date_from=now - timedelta(days=5), page_size=50)
    )
    assert any(r.article_id == art_reuters.id for r in res_date.results)
    assert not any(r.article_id == art_bbc.id for r in res_date.results)


# -----------------------------------------------------------------------------
# 7. Pagination & Empty Query
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pagination_and_empty_query(db_session: AsyncSession):
    service = SearchService(db_session)
    # Empty query should return paginated list without crashing
    res_empty = await service.search(SearchFilterParams(q="", page=1, page_size=5))
    assert res_empty.page == 1
    assert res_empty.page_size == 5
    assert len(res_empty.results) <= 5


# -----------------------------------------------------------------------------
# 8. Search Suggestions & Autocomplete
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions(db_session: AsyncSession):
    await create_test_topic(db_session, "Cybersecurity Defense", "cyber-suggest")
    await create_test_entity(db_session, "Anthropic", "ORGANIZATION")

    service = SearchService(db_session)
    sug_res = await service.get_suggestions(query="cyber")
    assert len(sug_res.suggestions) >= 1
    assert any("cyber" in s.text.lower() for s in sug_res.suggestions)


# -----------------------------------------------------------------------------
# 9. Search History & Clearing
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_history_and_clearing(db_session: AsyncSession):
    user = await create_test_user(db_session, "hist_user")
    service = SearchService(db_session)

    # Perform a search
    await service.search(SearchFilterParams(q="Neural Networks History"), user_id=user.id)

    # Retrieve history
    hist = await service.get_user_search_history(user.id)
    assert len(hist.history) >= 1
    assert hist.history[0].query == "Neural Networks History"

    # Clear history
    clear_res = await service.clear_user_search_history(user.id)
    assert clear_res["success"] is True

    # Check empty
    hist_after = await service.get_user_search_history(user.id)
    assert len(hist_after.history) == 0


# -----------------------------------------------------------------------------
# 10. HTTP Endpoints Integration Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_api_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Public Search
        res = await client.get("/api/search?q=technology&page=1&page_size=10")
        assert res.status_code == 200
        data = res.json()
        assert "results" in data
        assert "total_results" in data
        assert "execution_time_ms" in data

        # 2. Autocomplete Suggestions
        sug_res = await client.get("/api/search/suggestions?q=tech")
        assert sug_res.status_code == 200
        assert "suggestions" in sug_res.json()

        # 3. Authenticated Search History
        reg_res = await client.post(
            "/api/auth/register",
            json={"email": f"search_api_{uuid.uuid4().hex[:6]}@example.com", "password": "Password123!", "full_name": "Search API User"},
        )
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Perform search with user token
        await client.get("/api/search?q=Artificial+Intelligence", headers=headers)

        # Get history
        hist_res = await client.get("/api/search/history", headers=headers)
        assert hist_res.status_code == 200
        assert len(hist_res.json()["history"]) >= 1

        # Delete history
        del_res = await client.delete("/api/search/history", headers=headers)
        assert del_res.status_code == 200
