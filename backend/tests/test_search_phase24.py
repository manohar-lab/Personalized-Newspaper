"""test_search_phase24.py — Phase 24 Comprehensive Intelligent News Search & Discovery Tests."""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.models.user import User
from app.models.topic import Topic
from app.models.entity import Entity
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.models.interest import UserInterest
from app.models.action import UserArticleAction
from app.models.reading_history import ReadingHistory
from app.models.personalization_settings import UserPersonalizationSettings
from app.story_intelligence.models import Story, StoryArticle
from app.search.search_service import SearchService
from app.search.schemas import SearchFilterParams
from app.search.query_parser import QueryParser
from app.learning.evidence_models import UserInterestEvidence


async def create_user(db: AsyncSession, prefix: str = "u") -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"{prefix}_{uid}@example.com",
        password_hash="hashed_pw_test",
        full_name=f"User {uid}",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_topic(db: AsyncSession, name: str, slug: str) -> Topic:
    topic = Topic(name=name, slug=slug, description=f"Description for {name}")
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


async def create_entity(db: AsyncSession, name: str, entity_type: str = "COMPANY") -> Entity:
    norm = name.lower().replace(" ", "_")
    ent = Entity(name=name, normalized_name=f"{norm}_{uuid.uuid4().hex[:4]}", entity_type=entity_type)
    db.add(ent)
    await db.commit()
    await db.refresh(ent)
    return ent


async def create_article(
    db: AsyncSession,
    title: str,
    category: str = "TECHNOLOGY",
    content: str = "Article content description.",
    topics=None,
    entities=None,
    source_name: str = "Tech Today",
    published_at: datetime = None,
    language: str = "en",
    author: str = "Jane Reporter",
    is_paywalled: bool = False,
    extraction_status: str = "SUCCESS",
) -> Article:
    now = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    art = Article(
        title=title,
        slug=f"art-{uid}",
        source_url=f"https://example.com/art-{uid}",
        canonical_url=f"https://example.com/art-{uid}",
        source_name=source_name,
        description=content[:100],
        content=content,
        language=language,
        published_at=published_at or now,
        status="PUBLISHED",
        extraction_status=extraction_status if not is_paywalled else "PAYWALL",
        reading_time_minutes=3,
        author=author,
        is_full_text_available=(extraction_status == "SUCCESS" and not is_paywalled),
    )
    if topics:
        art.topics = topics
    if entities:
        art.entities = entities

    db.add(art)
    await db.flush()

    analysis = ArticleAnalysis(
        article_id=art.id,
        primary_category=category,
        summary=f"Summary of {title}",
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(art)
    return art


async def create_story(
    db: AsyncSession,
    title: str,
    primary_topic: Topic,
    summary: str = "Story summary",
    article_count: int = 3,
) -> Story:
    uid = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    story = Story(
        title=title,
        slug=f"story-{uid}",
        summary=summary,
        status="ACTIVE",
        primary_topic_id=primary_topic.id,
        importance_score=0.9,
        quality_score=0.85,
        article_count=article_count,
        source_count=2,
        first_published_at=now - timedelta(hours=5),
        last_updated_at=now,
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story


# =============================================================================
# 1. Exact headline & partial keyword search
# =============================================================================
@pytest.mark.asyncio
async def test_exact_headline_and_partial_keyword_search(db_session: AsyncSession):
    topic = await create_topic(db_session, "Artificial Intelligence", f"ai-{uuid.uuid4().hex[:6]}")
    art_exact = await create_article(
        db_session,
        title="OpenAI Releases Revolutionary Reasoning Model",
        topics=[topic],
    )
    art_other = await create_article(
        db_session,
        title="Automotive Market Dynamics in Europe",
        topics=[topic],
    )

    service = SearchService(db_session)

    # Exact headline search
    res_exact = await service.search(SearchFilterParams(q="OpenAI Releases Revolutionary Reasoning Model"))
    assert res_exact.total_results >= 1
    assert res_exact.articles[0].article_id == art_exact.id
    assert res_exact.articles[0].match_explanation == "Headline match"

    # Partial keyword search
    res_partial = await service.search(SearchFilterParams(q="reasoning model"))
    assert any(a.article_id == art_exact.id for a in res_partial.articles)


# =============================================================================
# 2. Case-insensitive, empty, and invalid queries
# =============================================================================
@pytest.mark.asyncio
async def test_query_normalization_and_edge_cases(db_session: AsyncSession):
    topic = await create_topic(db_session, "Quantum Computing", f"qc-{uuid.uuid4().hex[:6]}")
    art = await create_article(
        db_session,
        title="Superconducting Qubits Achieve Low Error Rates",
        topics=[topic],
    )

    service = SearchService(db_session)

    # Case-insensitive
    res_upper = await service.search(SearchFilterParams(q="SUPERCONDUCTING QUBITS"))
    assert any(a.article_id == art.id for a in res_upper.articles)

    # Excess whitespace and punctuation
    res_dirty = await service.search(SearchFilterParams(q="   superconducting   qubits???!!!   "))
    assert any(a.article_id == art.id for a in res_dirty.articles)

    # Empty query returns articles without crashing
    res_empty = await service.search(SearchFilterParams(q="", page_size=5))
    assert res_empty.page == 1
    assert len(res_empty.articles) <= 5

    # Very long query truncation
    long_q = "quantum " * 100
    res_long = await service.search(SearchFilterParams(q=long_q))
    assert res_long.query is not None


# =============================================================================
# 3. Topic, Entity, and Story Multi-Domain Search
# =============================================================================
@pytest.mark.asyncio
async def test_topic_entity_and_story_search(db_session: AsyncSession):
    tag = uuid.uuid4().hex[:6]
    topic_name = f"Robotics Innovation {tag}"
    topic = await create_topic(db_session, topic_name, f"robotics-{tag}")
    entity = await create_entity(db_session, f"Boston Dynamics {tag}", "COMPANY")

    story = await create_story(
        db_session,
        title=f"New Humanoid Robot Unveiled in {tag}",
        primary_topic=topic,
        summary="A new autonomous robot has been demonstrated.",
    )

    art = await create_article(
        db_session,
        title=f"Autonomous Bipedal Robotics Milestone {tag}",
        topics=[topic],
        entities=[entity],
    )

    service = SearchService(db_session)
    res = await service.search(SearchFilterParams(q=tag))

    # Stories, topics, and entities sections populated
    assert res.total_counts["stories"] >= 1
    assert any(s.id == story.id for s in res.stories)
    assert any(t.id == topic.id for t in res.topics)
    assert any(e.id == entity.id for e in res.entities)
    assert any(a.article_id == art.id for a in res.articles)


# =============================================================================
# 4. Personalized Ranking & Muted Topic Handling
# =============================================================================
@pytest.mark.asyncio
async def test_personalized_search_and_muted_topics(db_session: AsyncSession):
    tag = uuid.uuid4().hex[:6]
    topic_fav = await create_topic(db_session, f"AI Research {tag}", f"ai-{tag}")
    topic_mute = await create_topic(db_session, f"Celebrity Gossip {tag}", f"gossip-{tag}")

    user = await create_user(db_session, "pers_u")

    # Follow AI, Mute Gossip
    db_session.add(UserInterest(user_id=user.id, topic_id=topic_fav.id, interest_score=1.0, preference_type="POSITIVE", source="EXPLICIT"))
    db_session.add(UserInterest(user_id=user.id, topic_id=topic_mute.id, interest_score=0.0, preference_type="NEGATIVE", source="EXPLICIT"))
    await db_session.commit()

    art_fav = await create_article(
        db_session,
        title=f"Breakthrough Neural Architecture {tag}",
        category="TECHNOLOGY",
        topics=[topic_fav],
    )
    art_mute = await create_article(
        db_session,
        title=f"Viral Celebrity Scandal Update {tag}",
        category="ENTERTAINMENT",
        topics=[topic_mute],
    )

    service = SearchService(db_session)
    # Search for general keyword matching both
    res = await service.search(SearchFilterParams(q=tag), user_id=user.id)

    # Favorite should rank ahead of muted
    idx_fav = next((i for i, a in enumerate(res.articles) if a.article_id == art_fav.id), 99)
    idx_mute = next((i for i, a in enumerate(res.articles) if a.article_id == art_mute.id), 99)
    assert idx_fav < idx_mute


# =============================================================================
# 5. Read/Unread and Saved/Unsaved Filters
# =============================================================================
@pytest.mark.asyncio
async def test_read_unread_and_saved_filters(db_session: AsyncSession):
    user = await create_user(db_session, "filter_u")
    tag = uuid.uuid4().hex[:6]

    art_read = await create_article(db_session, title=f"Read Article {tag}")
    art_saved = await create_article(db_session, title=f"Saved Article {tag}")
    art_fresh = await create_article(db_session, title=f"Fresh Unread Article {tag}")

    # Mark art_read as read in ReadingHistory
    db_session.add(ReadingHistory(user_id=user.id, article_id=art_read.id))
    # Mark art_saved as saved in UserArticleAction
    db_session.add(UserArticleAction(user_id=user.id, article_id=art_saved.id, action="SAVE"))
    await db_session.commit()

    service = SearchService(db_session)

    # Filter: Read only
    res_read = await service.search(SearchFilterParams(q=tag, read_status="read"), user_id=user.id)
    assert any(a.article_id == art_read.id for a in res_read.articles)
    assert not any(a.article_id == art_fresh.id for a in res_read.articles)

    # Filter: Unread only
    res_unread = await service.search(SearchFilterParams(q=tag, read_status="unread"), user_id=user.id)
    assert not any(a.article_id == art_read.id for a in res_unread.articles)
    assert any(a.article_id == art_fresh.id for a in res_unread.articles)

    # Filter: Saved only
    res_saved = await service.search(SearchFilterParams(q=tag, saved_status="saved"), user_id=user.id)
    assert any(a.article_id == art_saved.id for a in res_saved.articles)
    assert not any(a.article_id == art_fresh.id for a in res_saved.articles)


# =============================================================================
# 6. Date Range Filters (24h, 7d, 30d)
# =============================================================================
@pytest.mark.asyncio
async def test_date_range_presets(db_session: AsyncSession):
    tag = uuid.uuid4().hex[:6]
    now = datetime.now(timezone.utc)

    art_recent = await create_article(db_session, title=f"Hours Old News {tag}", published_at=now - timedelta(hours=3))
    art_old = await create_article(db_session, title=f"Old Archives {tag}", published_at=now - timedelta(days=15))

    service = SearchService(db_session)

    # Preset: last_24_hours
    res_24h = await service.search(SearchFilterParams(q=tag, date_preset="last_24_hours"))
    assert any(a.article_id == art_recent.id for a in res_24h.articles)
    assert not any(a.article_id == art_old.id for a in res_24h.articles)

    # Preset: last_30_days includes both
    res_30d = await service.search(SearchFilterParams(q=tag, date_preset="last_30_days"))
    assert any(a.article_id == art_recent.id for a in res_30d.articles)
    assert any(a.article_id == art_old.id for a in res_30d.articles)


# =============================================================================
# 7. Sorting: Relevance vs Newest vs Importance
# =============================================================================
@pytest.mark.asyncio
async def test_sorting_modes(db_session: AsyncSession):
    tag = uuid.uuid4().hex[:6]
    now = datetime.now(timezone.utc)

    # Older article with high relevance keyword
    art_older_rel = await create_article(
        db_session,
        title=f"Core Fundamental Deep Learning {tag}",
        published_at=now - timedelta(days=5),
    )
    # Newer article with lower keyword concentration
    art_newer = await create_article(
        db_session,
        title=f"Recent Mention of Learning {tag}",
        published_at=now - timedelta(hours=1),
    )

    service = SearchService(db_session)

    # Sort by Newest First
    res_newest = await service.search(SearchFilterParams(q=tag, sort_by="newest"))
    matches_newest = [a for a in res_newest.articles if tag in a.title]
    assert matches_newest[0].article_id == art_newer.id

    # Sort by Relevance
    res_rel = await service.search(SearchFilterParams(q=f"Deep Learning {tag}", sort_by="relevance"))
    matches_rel = [a for a in res_rel.articles if tag in a.title]
    assert matches_rel[0].article_id == art_older_rel.id


# =============================================================================
# 8. Deduplication
# =============================================================================
@pytest.mark.asyncio
async def test_duplicate_suppression(db_session: AsyncSession):
    tag = uuid.uuid4().hex[:6]
    title_shared = f"Syndicated Wire Story Regarding Economy {tag}"

    # Two articles with identical headline
    art1 = await create_article(db_session, title=title_shared, source_name="Wire A")
    art2 = await create_article(db_session, title=title_shared, source_name="Wire B")

    service = SearchService(db_session)

    # With deduplicate=True
    res_dedup = await service.search(SearchFilterParams(q=tag, deduplicate=True))
    matches = [a for a in res_dedup.articles if tag in a.title]
    assert len(matches) == 1

    # With deduplicate=False
    res_raw = await service.search(SearchFilterParams(q=tag, deduplicate=False))
    matches_raw = [a for a in res_raw.articles if tag in a.title]
    assert len(matches_raw) >= 2


# =============================================================================
# 9. Autocomplete Suggestions Privacy & User Isolation
# =============================================================================
@pytest.mark.asyncio
async def test_suggestions_privacy_and_user_isolation(db_session: AsyncSession):
    user_a = await create_user(db_session, "user_a")
    user_b = await create_user(db_session, "user_b")

    service = SearchService(db_session)

    # User A searches for secret query
    secret_q = f"Confidential merger discussions {uuid.uuid4().hex[:4]}"
    await service.search(SearchFilterParams(q=secret_q), user_id=user_a.id)

    # User A gets suggestions containing their secret
    sug_a = await service.get_suggestions(query="Confidential", user_id=user_a.id)
    assert any("Confidential" in s.text for s in sug_a.suggestions)

    # User B should NOT receive User A's private query
    sug_b = await service.get_suggestions(query="Confidential", user_id=user_b.id)
    assert not any(secret_q in s.text for s in sug_b.suggestions)


# =============================================================================
# 10. Recent Searches Storage, Clearing, and User Isolation
# =============================================================================
@pytest.mark.asyncio
async def test_recent_searches_and_clearing(db_session: AsyncSession):
    user_a = await create_user(db_session, "hist_a")
    user_b = await create_user(db_session, "hist_b")

    service = SearchService(db_session)

    # User A submits searches
    q1 = f"AI Ethics {uuid.uuid4().hex[:4]}"
    q2 = f"Quantum Algorithms {uuid.uuid4().hex[:4]}"
    await service.search(SearchFilterParams(q=q1), user_id=user_a.id)
    await service.search(SearchFilterParams(q=q2), user_id=user_a.id)

    # User B submits search
    q_b = f"Solar Batteries {uuid.uuid4().hex[:4]}"
    await service.search(SearchFilterParams(q=q_b), user_id=user_b.id)

    # Verify User A's history
    hist_a = await service.get_user_recent_searches(user_a.id)
    queries_a = [r.query for r in hist_a.recent]
    assert q1 in queries_a
    assert q2 in queries_a
    assert q_b not in queries_a  # User B's search isolated

    # Clear User A's history
    clear_res = await service.clear_user_search_history(user_a.id)
    assert clear_res["success"] is True

    # User A history now empty
    hist_a_empty = await service.get_user_recent_searches(user_a.id)
    assert len(hist_a_empty.recent) == 0

    # User B history untouched
    hist_b = await service.get_user_recent_searches(user_b.id)
    assert any(r.query == q_b for r in hist_b.recent)


# =============================================================================
# 11. Search Learning Integration & Paused-Learning Behavior
# =============================================================================
@pytest.mark.asyncio
async def test_search_learning_and_paused_state(db_session: AsyncSession):
    user = await create_user(db_session, "learn_u")
    service = SearchService(db_session)

    # Active learning state
    q_active = f"Machine Learning Research {uuid.uuid4().hex[:4]}"
    await service.search(SearchFilterParams(q=q_active), user_id=user.id)

    # Check that behavioral evidence was logged
    stmt_ev = select(UserInterestEvidence).where(
        UserInterestEvidence.user_id == user.id,
        UserInterestEvidence.signal_type == "SEARCH",
        UserInterestEvidence.target_name == q_active,
    )
    ev_active = (await db_session.execute(stmt_ev)).scalars().first()
    assert ev_active is not None
    assert ev_active.strength > 0.0

    # Pause learning in UserPersonalizationSettings
    db_session.add(
        UserPersonalizationSettings(
            user_id=user.id,
            learning_enabled=False,
        )
    )
    await db_session.commit()

    q_paused = f"Paused Search Term {uuid.uuid4().hex[:4]}"
    await service.search(SearchFilterParams(q=q_paused), user_id=user.id)

    # Under paused learning, signal strength must be 0.0
    stmt_ev_paused = select(UserInterestEvidence).where(
        UserInterestEvidence.user_id == user.id,
        UserInterestEvidence.signal_type == "SEARCH",
        UserInterestEvidence.target_name == q_paused,
    )
    ev_paused = (await db_session.execute(stmt_ev_paused)).scalars().first()
    assert ev_paused is not None
    assert ev_paused.strength == 0.0


# =============================================================================
# 12. HTTP Endpoints (/api/search/recent, /api/search/filters)
# =============================================================================
@pytest.mark.asyncio
async def test_search_http_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Filters metadata endpoint
        filters_res = await client.get("/api/search/filters")
        assert filters_res.status_code == 200
        f_data = filters_res.json()
        assert "categories" in f_data
        assert "date_presets" in f_data
        assert "sort_options" in f_data
        assert "result_types" in f_data

        # Register user for auth testing
        email = f"search_http_{uuid.uuid4().hex[:6]}@example.com"
        reg = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "Password123!", "full_name": "HTTP Searcher"},
        )
        token = reg.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Perform search with user token
        search_res = await client.get("/api/search?q=Biotechnology", headers=auth_headers)
        assert search_res.status_code == 200
        s_data = search_res.json()
        assert "stories" in s_data
        assert "articles" in s_data
        assert "topics" in s_data
        assert "entities" in s_data
        assert "total_counts" in s_data

        # Get recent searches
        recent_res = await client.get("/api/search/recent", headers=auth_headers)
        assert recent_res.status_code == 200
        assert "recent" in recent_res.json()
        assert len(recent_res.json()["recent"]) >= 1

        # Clear recent searches
        del_recent = await client.delete("/api/search/recent", headers=auth_headers)
        assert del_recent.status_code == 200
        assert del_recent.json()["success"] is True

        # Verify cleared
        recent_after = await client.get("/api/search/recent", headers=auth_headers)
        assert len(recent_after.json()["recent"]) == 0
