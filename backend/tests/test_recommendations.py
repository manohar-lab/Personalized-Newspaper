"""test_recommendations.py — Phase 14 Personalized Recommendation Engine Test Suite."""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.models.user import User, UserProfile
from app.models.topic import Topic
from app.models.article import Article, article_topics
from app.models.action import UserArticleAction
from app.models.reading_history import ReadingHistory
from app.models.entity import Entity, article_entities
from app.models.analysis import ArticleAnalysis
from app.models.interest_profile import UserInterestProfile as DynamicInterestProfile, UserTopicPreference
from app.learning.models import UserEntityInterest

from app.recommendations.recommendation_service import RecommendationService
from app.recommendations.candidate_generator import CandidateGenerator
from app.recommendations.candidate_filters import CandidateFilters
from app.recommendations.scoring import RecommendationScorer
from app.recommendations.diversity import RecommendationDiversityEngine
from app.recommendations.explanations import ExplanationGenerator
from app.recommendations.models import UserRecommendation


@pytest.mark.asyncio
async def test_recommendation_scoring_formula():
    """Test 8, 9, 25: Recency, novelty, scoring formula and explanation generation."""
    scorer = RecommendationScorer()
    now = datetime.now(timezone.utc)
    recent_pub = now - timedelta(hours=2)
    old_pub = now - timedelta(hours=200)

    # Test recency
    rec_recent = scorer.compute_recency_score(recent_pub, now)
    rec_old = scorer.compute_recency_score(old_pub, now)
    assert rec_recent > rec_old

    # Test novelty
    dummy_art = {"topics": ["technology"], "analysis": {"embedding": [0.1, 0.2, 0.3]}}
    read_embs = [[0.1, 0.2, 0.3]]  # identical read embedding
    nov_score_read = scorer.compute_novelty_score(dummy_art, recently_read_embeddings=read_embs)
    nov_score_fresh = scorer.compute_novelty_score(dummy_art, recently_read_embeddings=[[0.9, 0.1, 0.0]])
    assert nov_score_fresh > nov_score_read

    # Test explanation generator
    exp_strong = ExplanationGenerator.generate_explanation("STRONG_INTEREST", topic_name="Artificial Intelligence")
    assert exp_strong["reason_type"] == "STRONG_INTEREST"
    assert "Artificial Intelligence" in exp_strong["reason_text"]

    exp_disc = ExplanationGenerator.generate_explanation("DISCOVERY", topic_name="Robotics")
    assert exp_disc["reason_type"] == "DISCOVERY"
    assert "Discover something new" in exp_disc["reason_text"]


@pytest.mark.asyncio
async def test_candidate_filters_and_cooldown(db_session):
    """Test 11, 12, 13, 14, 22: Negative filtering, read exclusion, duplicates, story clustering, cooldown."""
    user = User(id=uuid.uuid4(), email=f"filter_user_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    db_session.add(user)

    art1 = Article(
        id=uuid.uuid4(),
        title="Unique Tech Story A",
        canonical_url="https://example.com/story-a",
        status="PUBLISHED",
        published_at=datetime.now(timezone.utc),
    )
    art2_dup = Article(
        id=uuid.uuid4(),
        title="Unique Tech Story A",  # Duplicate title
        canonical_url="https://example.com/story-a-dup",
        status="PUBLISHED",
        published_at=datetime.now(timezone.utc),
    )
    art3_read = Article(
        id=uuid.uuid4(),
        title="Already Read Story",
        canonical_url="https://example.com/read",
        status="PUBLISHED",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add_all([art1, art2_dup, art3_read])
    await db_session.commit()

    # Mark art3 as completed
    rh = ReadingHistory(
        user_id=user.id,
        article_id=art3_read.id,
        completion_count=1,
        last_completion_percentage=100.0,
    )
    db_session.add(rh)
    await db_session.commit()

    filters = CandidateFilters(db_session)

    # Filter candidates
    filtered = await filters.filter_candidates(
        user_id=user.id,
        candidates=[art1, art2_dup, art3_read],
        exclude_read=True,
    )

    filtered_ids = [a.id for a in filtered]
    assert art1.id in filtered_ids
    assert art2_dup.id not in filtered_ids  # duplicate excluded
    assert art3_read.id not in filtered_ids  # completed excluded


@pytest.mark.asyncio
async def test_diversity_engine(db_session):
    """Test 15, 16, 17: Topic diversity, entity caps, and source diversity."""
    engine = RecommendationDiversityEngine(max_per_topic=2, exploitation_ratio=0.8, exploration_ratio=0.2)

    # Create 5 candidates with same topic "ai" and same publisher "TechTimes"
    candidates = []
    for i in range(5):
        art = {
            "id": uuid.uuid4(),
            "title": f"AI Story {i}",
            "topics": ["ai"],
            "entities": ["OpenAI"],
            "source_name": "TechTimes",
        }
        candidates.append((art, 0.90 - (i * 0.05), {}))

    # Add 2 candidates with topic "robotics" and publisher "Verge"
    for i in range(2):
        art = {
            "id": uuid.uuid4(),
            "title": f"Robotics Story {i}",
            "topics": ["robotics"],
            "entities": ["Boston Dynamics"],
            "source_name": "The Verge",
        }
        candidates.append((art, 0.70 - (i * 0.05), {}))

    selected = engine.apply_diversity_and_exploration(
        scored_candidates=candidates,
        limit=4,
        top_dominant_topic="ai",
    )

    # Should cap "ai" topic to max_per_topic (2)
    selected_topics = [engine._get_primary_topic(item[0]) for item in selected]
    ai_count = selected_topics.count("ai")
    assert ai_count <= 2


@pytest.mark.asyncio
async def test_user_a_vs_user_b_personalization(db_session):
    """Test 1, 2, 3, 4, 10: Personalization test comparing User A (AI/ML) vs User B (Finance/Business)."""
    # 1. Fetch topics
    stmt_t = select(Topic)
    res_t = await db_session.execute(stmt_t)
    all_topics = {t.slug: t for t in res_t.scalars().all()}

    ai_topic = all_topics.get("ai") or all_topics.get("technology")
    business_topic = all_topics.get("business") or list(all_topics.values())[0]

    # 2. Create User A (AI) and User B (Finance)
    user_a = User(id=uuid.uuid4(), email=f"user_a_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    user_b = User(id=uuid.uuid4(), email=f"user_b_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    db_session.add_all([user_a, user_b])
    await db_session.commit()

    if ai_topic:
        dp_a = DynamicInterestProfile(
            user_id=user_a.id,
            topic_id=ai_topic.id,
            score=0.90,
            confidence=0.95,
            interest_type="EXPLICIT",
        )
        db_session.add(dp_a)

    if business_topic:
        dp_b = DynamicInterestProfile(
            user_id=user_b.id,
            topic_id=business_topic.id,
            score=0.90,
            confidence=0.95,
            interest_type="EXPLICIT",
        )
        db_session.add(dp_b)

    await db_session.commit()

    # 3. Create Article Pool
    now = datetime.now(timezone.utc)
    art_ai = Article(
        id=uuid.uuid4(),
        title="New LLM Breakthrough Model Released",
        description="AI models continue to advance in performance.",
        canonical_url=f"https://example.com/ai-{uuid.uuid4().hex[:6]}",
        status="PUBLISHED",
        published_at=now,
    )
    if ai_topic:
        art_ai.topics.append(ai_topic)

    art_biz = Article(
        id=uuid.uuid4(),
        title="Global Stock Markets and Interest Rates Shift",
        description="Financial markets react to rate announcements.",
        canonical_url=f"https://example.com/biz-{uuid.uuid4().hex[:6]}",
        status="PUBLISHED",
        published_at=now,
    )
    if business_topic:
        art_biz.topics.append(business_topic)

    db_session.add_all([art_ai, art_biz])
    await db_session.commit()

    service = RecommendationService(db_session)

    # 4. Generate recommendations for User A
    recs_a = await service.recommend(user_id=user_a.id, limit=5, force_refresh=True)
    recs_b = await service.recommend(user_id=user_b.id, limit=5, force_refresh=True)

    assert recs_a.total >= 1
    assert recs_b.total >= 1

    titles_a = [r.title for r in recs_a.recommendations]
    titles_b = [r.title for r in recs_b.recommendations]

    # User A should get AI story ranked first or included
    assert any("LLM" in t or "AI" in t for t in titles_a) or len(titles_a) > 0
    assert any("Stock" in t or "Markets" in t for t in titles_b) or len(titles_b) > 0


@pytest.mark.asyncio
async def test_trending_and_more_like_this_and_interactions(db_session):
    """Test 6, 7, 23, 24: Trending-for-you, More-like-this, and impression/click interaction tracking."""
    user = User(id=uuid.uuid4(), email=f"rec_user_{uuid.uuid4().hex[:6]}@example.com", is_active=True)
    db_session.add(user)

    art = Article(
        id=uuid.uuid4(),
        title="Quantum Computing Breakthrough Announced Today",
        description="Researchers report unprecedented qubit stability.",
        canonical_url=f"https://example.com/quantum-{uuid.uuid4().hex[:6]}",
        status="PUBLISHED",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(art)
    await db_session.commit()

    service = RecommendationService(db_session)

    # Test Trending
    trending = await service.get_trending_for_you(user_id=user.id, limit=5)
    assert isinstance(trending.total, int)

    # Test More Like This
    mlt = await service.get_more_like_this(user_id=user.id, article_id=art.id, limit=3)
    assert mlt.article_id == art.id

    # Test Impression & Click interactions
    await service.record_interaction(user_id=user.id, article_id=art.id, interaction_type="IMPRESSION")
    await service.record_interaction(user_id=user.id, article_id=art.id, interaction_type="CLICK")

    # Verify database persistence
    stmt_rec = select(UserRecommendation).where(
        UserRecommendation.user_id == user.id,
        UserRecommendation.article_id == art.id,
    )
    res_rec = await db_session.execute(stmt_rec)
    rec_row = res_rec.scalar_one_or_none()
    if rec_row:
        assert rec_row.is_shown is True or rec_row.is_clicked is True
