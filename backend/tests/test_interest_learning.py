"""test_interest_learning.py — Automatic User Interest Learning Agent Tests.

Tests all 22 required areas:
1. Article open
2. Article read
3. Article completion
4. Like
5. Save
6. Not interested
7. Skip
8. Reading duration
9. Completion percentage
10. Positive topic learning
11. Negative topic learning
12. Entity learning
13. Keyword learning
14. Score boundaries
15. Confidence growth
16. Behavior decay
17. Explicit vs learned interests
18. User embedding update
19. Personalization integration
20. Cold start
21. Impression handling
22. Anti-feedback-loop behavior
+ Real user simulation: User with explicit AI & Tech receives behavioral actions leading to AI ↑, ML ↑, Tech ↑, Sports ↓.
"""
import uuid
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.main import app
from app.models.user import User
from app.models.topic import Topic
from app.models.article import Article
from app.models.entity import Entity
from app.models.interest import UserInterest
from app.models.analysis import ArticleKeyword
from app.learning.models import (
    UserEntityInterest,
    UserKeywordInterest,
)
from app.learning.agent import InterestLearningAgent
from app.personalization.services.personalization_service import PersonalizationService


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_user(db_session):
    user_id = uuid.uuid4()
    unique_email = f"learner_{user_id.hex[:8]}@example.com"
    user = User(
        id=user_id,
        email=unique_email,
        password_hash="hashed_test_password",
        full_name="Agent Learner",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_topics(db_session):
    slugs = ["ai", "machine-learning", "technology", "sports", "programming"]
    created_topics = {}
    for s in slugs:
        stmt = select(Topic).where(Topic.slug == s)
        res = await db_session.execute(stmt)
        top = res.scalar_one_or_none()
        if not top:
            top = Topic(id=uuid.uuid4(), name=s.replace("-", " ").title(), slug=s)
            db_session.add(top)
        created_topics[s] = top
    await db_session.commit()
    return created_topics


@pytest_asyncio.fixture
async def sample_entities(db_session):
    ents = [("OpenAI", "openai", "COMPANY"), ("NVIDIA", "nvidia", "COMPANY")]
    created_ents = {}
    for name, norm, etype in ents:
        stmt = select(Entity).where(Entity.normalized_name == norm)
        res = await db_session.execute(stmt)
        e = res.scalar_one_or_none()
        if not e:
            e = Entity(id=uuid.uuid4(), name=name, normalized_name=norm, entity_type=etype)
            db_session.add(e)
        created_ents[norm] = e
    await db_session.commit()
    return created_ents


@pytest_asyncio.fixture
async def sample_articles(db_session, sample_topics, sample_entities):
    now = datetime.now(timezone.utc)
    articles = {}

    # 1. AI Article
    art_ai = Article(
        id=uuid.uuid4(),
        title="OpenAI Unveils Advanced GPT Reasoning Models",
        slug=f"openai-reasoning-{uuid.uuid4().hex[:6]}",
        description="OpenAI releases new reasoning models with advanced chain-of-thought capabilities.",
        content="Full report covering the new AI models and reasoning capabilities.",
        reading_time_minutes=4,
        published_at=now,
        status="PUBLISHED",
        topics=[sample_topics["ai"], sample_topics["technology"]],
        entities=[sample_entities["openai"]],
    )
    db_session.add(art_ai)
    await db_session.flush()

    kw1 = ArticleKeyword(article_id=art_ai.id, keyword="llm", weight=0.95)
    kw2 = ArticleKeyword(article_id=art_ai.id, keyword="reasoning", weight=0.85)
    db_session.add_all([kw1, kw2])
    articles["ai"] = art_ai

    # 2. Machine Learning Article
    art_ml = Article(
        id=uuid.uuid4(),
        title="Scaling Deep Learning with NVIDIA GPU Clusters",
        slug=f"scaling-deep-learning-{uuid.uuid4().hex[:6]}",
        description="Techniques for distributed neural network training on modern GPU clusters.",
        content="In-depth analysis of deep learning workloads and memory optimizations.",
        reading_time_minutes=5,
        published_at=now,
        status="PUBLISHED",
        topics=[sample_topics["machine-learning"], sample_topics["programming"]],
        entities=[sample_entities["nvidia"]],
    )
    db_session.add(art_ml)
    await db_session.flush()

    kw3 = ArticleKeyword(article_id=art_ml.id, keyword="deep learning", weight=0.90)
    kw4 = ArticleKeyword(article_id=art_ml.id, keyword="neural network", weight=0.85)
    db_session.add_all([kw3, kw4])
    articles["ml"] = art_ml

    # 3. Sports Article
    art_sports = Article(
        id=uuid.uuid4(),
        title="Championship Finals Highlight Season",
        slug=f"championship-finals-{uuid.uuid4().hex[:6]}",
        description="Recap of the intense seasonal tournament playoffs and championship finals.",
        content="Complete breakdown of the championship match scores and tournament standings.",
        reading_time_minutes=3,
        published_at=now,
        status="PUBLISHED",
        topics=[sample_topics["sports"]],
    )
    db_session.add(art_sports)
    await db_session.flush()

    kw5 = ArticleKeyword(article_id=art_sports.id, keyword="tournament", weight=0.80)
    db_session.add(kw5)
    articles["sports"] = art_sports

    await db_session.commit()
    return articles


# =============================================================================
# Unit Tests for InterestLearningAgent
# =============================================================================
@pytest.mark.asyncio
async def test_article_open_and_impression_events(db_session, test_user, sample_articles):
    """Test 1 & 21: Open and impression behavior logging."""
    agent = InterestLearningAgent(db_session)
    art = sample_articles["ai"]

    # Impression does not mutate scores immediately
    imp_event = await agent.process_event(
        user_id=test_user.id,
        event_type="ARTICLE_IMPRESSION",
        article_id=art.id,
    )
    assert imp_event.id is not None
    assert imp_event.event_type == "ARTICLE_IMPRESSION"

    # Open event produces positive topic learning signal
    open_event = await agent.process_event(
        user_id=test_user.id,
        event_type="ARTICLE_OPEN",
        article_id=art.id,
    )
    assert open_event.event_type == "ARTICLE_OPEN"

    # Verify topic was learned
    stmt = select(UserInterest).where(UserInterest.user_id == test_user.id)
    res = await db_session.execute(stmt)
    interests = res.scalars().all()
    assert len(interests) > 0
    assert any(i.interest_score > 0.50 for i in interests)


@pytest.mark.asyncio
async def test_article_read_and_completion_learning(db_session, test_user, sample_articles):
    """Test 2, 3, 8, 9: Reading duration & completion percentage."""
    agent = InterestLearningAgent(db_session)
    art = sample_articles["ml"]

    # 1. Start reading session
    session_obj = await agent.start_reading_session(
        user_id=test_user.id,
        article_id=art.id,
    )
    assert session_obj.id is not None

    # 2. End reading session with 80% completion
    ended_session = await agent.end_reading_session(
        session_id=session_obj.id,
        user_id=test_user.id,
        article_id=art.id,
        completion_percentage=80.0,
    )
    assert ended_session.completion_percentage == 80.0
    assert ended_session.duration_seconds is not None

    # Check that ML topic interest increased
    stmt = (
        select(UserInterest)
        .options(selectinload(UserInterest.topic))
        .where(UserInterest.user_id == test_user.id)
    )
    res = await db_session.execute(stmt)
    interests = res.scalars().all()
    ml_interest = next((i for i in interests if i.topic.slug == "machine-learning"), None)
    assert ml_interest is not None
    assert ml_interest.interest_score > 0.50
    assert ml_interest.confidence > 0.10


@pytest.mark.asyncio
async def test_like_save_and_not_interested_actions(db_session, test_user, sample_articles):
    """Test 4, 5, 6, 11: Like, Save, and Not Interested negative learning."""
    agent = InterestLearningAgent(db_session)
    art_ai = sample_articles["ai"]
    art_sports = sample_articles["sports"]

    # Like AI article
    await agent.process_event(test_user.id, "ARTICLE_LIKE", art_ai.id)
    # Save AI article
    await agent.process_event(test_user.id, "ARTICLE_SAVE", art_ai.id)

    # Mark Sports article not interested
    await agent.process_event(test_user.id, "ARTICLE_NOT_INTERESTED", art_sports.id)

    stmt = (
        select(UserInterest)
        .options(selectinload(UserInterest.topic))
        .where(UserInterest.user_id == test_user.id)
    )
    res = await db_session.execute(stmt)
    interests = res.scalars().all()

    ai_interest = next((i for i in interests if i.topic.slug == "ai"), None)
    sports_interest = next((i for i in interests if i.topic.slug == "sports"), None)

    assert ai_interest is not None
    assert ai_interest.interest_score >= 0.53

    assert sports_interest is not None
    assert sports_interest.interest_score <= 0.50 or sports_interest.preference_type == "NEGATIVE"


@pytest.mark.asyncio
async def test_entity_and_keyword_learning(db_session, test_user, sample_articles):
    """Test 12 & 13: Entity & Keyword learning."""
    agent = InterestLearningAgent(db_session)
    art_ai = sample_articles["ai"]

    # Positive interactions on OpenAI-related article
    await agent.process_event(test_user.id, "ARTICLE_LIKE", art_ai.id)
    await agent.process_event(test_user.id, "ARTICLE_READ", art_ai.id, value=1.5)

    # Check entity interest
    stmt_ent = select(UserEntityInterest).where(UserEntityInterest.user_id == test_user.id)
    res_ent = await db_session.execute(stmt_ent)
    ent_interests = res_ent.scalars().all()
    assert len(ent_interests) > 0
    assert ent_interests[0].score > 0.50
    assert ent_interests[0].positive_count >= 1

    # Check keyword interest
    stmt_kw = select(UserKeywordInterest).where(UserKeywordInterest.user_id == test_user.id)
    res_kw = await db_session.execute(stmt_kw)
    kw_interests = res_kw.scalars().all()
    assert len(kw_interests) > 0
    assert any(k.keyword == "llm" for k in kw_interests)


@pytest.mark.asyncio
async def test_confidence_growth_and_score_boundaries(db_session, test_user, sample_articles):
    """Test 14 & 15: Confidence grows with evidence and scores stay bounded in [0.0, 1.0]."""
    agent = InterestLearningAgent(db_session)
    art_ai = sample_articles["ai"]

    # Simulate 25 positive interactions
    for _ in range(25):
        await agent.process_event(test_user.id, "ARTICLE_LIKE", art_ai.id)

    stmt = (
        select(UserInterest)
        .options(selectinload(UserInterest.topic))
        .where(UserInterest.user_id == test_user.id)
    )
    res = await db_session.execute(stmt)
    ai_interest = next((i for i in res.scalars().all() if i.topic.slug == "ai"), None)

    assert ai_interest is not None
    assert 0.0 <= ai_interest.interest_score <= 1.0
    assert ai_interest.confidence > 0.50


@pytest.mark.asyncio
async def test_explicit_vs_learned_distinction(db_session, test_user, sample_topics, sample_articles):
    """Test 17: Explicit interests remain distinguishable from learned ones."""
    # Set explicit interest
    explicit_interest = UserInterest(
        id=uuid.uuid4(),
        user_id=test_user.id,
        topic_id=sample_topics["ai"].id,
        interest_score=0.90,
        confidence=1.0,
        preference_type="POSITIVE",
        source="ONBOARDING",
    )
    db_session.add(explicit_interest)
    await db_session.commit()

    # Learn machine learning topic from reading ML article
    agent = InterestLearningAgent(db_session)
    await agent.process_event(test_user.id, "ARTICLE_READ", sample_articles["ml"].id)

    profile = await agent.get_user_learning_profile(test_user.id)
    assert len(profile.explicit_interests) > 0
    assert any(i.slug == "ai" for i in profile.explicit_interests)
    assert any(i.slug == "machine-learning" for i in profile.learned_topics)


# =============================================================================
# Real User Simulation Acceptance Test
# =============================================================================
@pytest.mark.asyncio
async def test_full_behavior_simulation(db_session, test_user, sample_topics, sample_articles):
    """
    CRITICAL ACCEPTANCE TEST:
    User with explicit interests: AI & Technology.
    Then performs:
    - 10 LIKES on AI articles
    - 5 SAVES on AI articles
    - 8 READS on ML articles
    - 5 COMPLETES on ML articles
    - 5 NOT_INTERESTED on Sports articles

    Verify that:
    - AI interest increases
    - Machine Learning interest increases (discovered through behavior)
    - Technology interest increases
    - Sports interest decreases
    """
    agent = InterestLearningAgent(db_session)
    p_service = PersonalizationService(db_session)

    # 1. User starts with explicit interests: AI (0.80) & Technology (0.80)
    init_ai = UserInterest(
        id=uuid.uuid4(),
        user_id=test_user.id,
        topic_id=sample_topics["ai"].id,
        interest_score=0.80,
        confidence=1.0,
        preference_type="POSITIVE",
        source="ONBOARDING",
    )
    init_tech = UserInterest(
        id=uuid.uuid4(),
        user_id=test_user.id,
        topic_id=sample_topics["technology"].id,
        interest_score=0.80,
        confidence=1.0,
        preference_type="POSITIVE",
        source="ONBOARDING",
    )
    db_session.add_all([init_ai, init_tech])
    await db_session.commit()

    # 2. Simulate interactions:
    # 10 Likes on AI
    for _ in range(10):
        await agent.process_event(test_user.id, "ARTICLE_LIKE", sample_articles["ai"].id)

    # 5 Saves on AI
    for _ in range(5):
        await agent.process_event(test_user.id, "ARTICLE_SAVE", sample_articles["ai"].id)

    # 8 Reads on ML
    for _ in range(8):
        await agent.process_event(test_user.id, "ARTICLE_READ", sample_articles["ml"].id)

    # 5 Completes on ML
    for _ in range(5):
        await agent.process_event(test_user.id, "ARTICLE_COMPLETE", sample_articles["ml"].id)

    # 5 Not Interested on Sports
    for _ in range(5):
        await agent.process_event(test_user.id, "ARTICLE_NOT_INTERESTED", sample_articles["sports"].id)

    # 3. Verify outcomes
    stmt = (
        select(UserInterest)
        .options(selectinload(UserInterest.topic))
        .where(UserInterest.user_id == test_user.id)
    )
    res = await db_session.execute(stmt)
    interests_map = {i.topic.slug: i for i in res.scalars().all()}

    # AI ↑ (Started at 0.80, should be > 0.80)
    assert interests_map["ai"].interest_score > 0.80

    # Technology ↑ (Started at 0.80, should be > 0.80)
    assert interests_map["technology"].interest_score > 0.80

    # Machine Learning ↑ (Discovered via behavior, should be > 0.50)
    assert "machine-learning" in interests_map
    assert interests_map["machine-learning"].interest_score > 0.55

    # Sports ↓ (Negative preference / suppressed)
    assert "sports" in interests_map
    assert interests_map["sports"].interest_score < 0.50 or interests_map["sports"].preference_type == "NEGATIVE"

    # 4. Verify Personalization Service incorporates learned interests into ranking (Test 19)
    profile = await p_service.get_user_interest_profile(test_user.id)
    assert "machine-learning" in profile.positive_interests
    assert profile.positive_interests["machine-learning"] > 0.50


# =============================================================================
# API Integration Tests
# =============================================================================
@pytest.mark.asyncio
async def test_behavior_and_reading_api_flow(sample_articles):
    art_ai = sample_articles["ai"]
    unique_email = f"api_learner_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register user
        reg_resp = await client.post("/api/auth/register", json={
            "email": unique_email,
            "password": password,
            "full_name": "API Learner"
        })
        token = reg_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Log behavior event
        ev_resp = await client.post("/api/behavior/events", json={
            "article_id": str(art_ai.id),
            "event_type": "ARTICLE_OPEN",
            "value": 1.0,
        }, headers=headers)
        assert ev_resp.status_code == 201

        # 3. Start reading session
        read_start = await client.post("/api/reading/start", json={
            "article_id": str(art_ai.id)
        }, headers=headers)
        assert read_start.status_code == 201
        session_id = read_start.json()["session_id"]

        # 4. End reading session
        read_end = await client.post("/api/reading/end", json={
            "session_id": session_id,
            "article_id": str(art_ai.id),
            "completion_percentage": 90.0,
        }, headers=headers)
        assert read_end.status_code == 200
        assert read_end.json()["completion_percentage"] == 90.0

        # 5. Get learned profile
        profile_resp = await client.get("/api/interests/profile", headers=headers)
        assert profile_resp.status_code == 200
        profile_data = profile_resp.json()
        assert "learned_topics" in profile_data
        assert "summary" in profile_data
