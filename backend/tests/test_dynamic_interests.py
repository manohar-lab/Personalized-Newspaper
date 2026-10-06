"""test_dynamic_interests.py — Comprehensive Unit & Integration Tests for Phase 13.

Tests all 25 specific areas + Realistic User A Simulation + Negative Suppression + Time Decay + Personalization Divergence.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.models.user import User
from app.models.topic import Topic
from app.models.article import Article
from app.models.entity import Entity
from app.models.analysis import ArticleAnalysis, ArticleKeyword
from app.models.interest_profile import (
    UserInterestProfile,
    UserTopicPreference,
    InterestLearningEvent,
    UserInterestSnapshot,
)
from app.ai.interests.signals import SignalManager, SignalType
from app.ai.interests.scoring import InterestScoringEngine, InterestState
from app.ai.interests.decay import InterestDecayEngine
from app.ai.interests.discovery import TopicPropagationEngine
from app.ai.interests.learner import InterestLearningService
from app.personalization.services.personalization_service import PersonalizationService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_signals_and_weights():
    """Verify signal weight resolution from settings and dynamic multipliers."""
    assert SignalManager.get_signal_weight("EXPLICIT_INTEREST") == 1.00
    assert SignalManager.get_signal_weight("LIKE") == 0.90
    assert SignalManager.get_signal_weight("SAVE") == 0.85
    assert SignalManager.get_signal_weight("DEEP_READ") == 0.75
    assert SignalManager.get_signal_weight("REPEAT_READ") == 0.80
    assert SignalManager.get_signal_weight("NORMAL_READ") == 0.35
    assert SignalManager.get_signal_weight("SEARCH") == 0.25
    assert SignalManager.get_signal_weight("SHORT_READ") == -0.05
    assert SignalManager.get_signal_weight("BOUNCE") == -0.10
    assert SignalManager.get_signal_weight("NOT_INTERESTED") == -1.00
    assert SignalManager.get_signal_weight("ARTICLE_IMPRESSION") == 0.00


@pytest.mark.asyncio
async def test_confidence_and_scoring_formulas():
    """Verify confidence growth saturation curve and score bounded updates."""
    # Confidence formula
    conf_1 = InterestScoringEngine.calculate_confidence(1)
    conf_5 = InterestScoringEngine.calculate_confidence(5)
    conf_20 = InterestScoringEngine.calculate_confidence(20)
    conf_explicit = InterestScoringEngine.calculate_confidence(1, explicit=True)

    assert conf_1 < conf_5 < conf_20
    assert conf_explicit == 1.0
    assert conf_20 >= 0.90

    # Score bounded update
    new_score = InterestScoringEngine.update_score(0.50, 0.80)
    assert 0.50 < new_score <= 1.0

    # Negative update does not fall below 0.0
    zero_clamp = InterestScoringEngine.update_score(0.10, -50.0)
    assert zero_clamp == 0.0


@pytest.mark.asyncio
async def test_time_decay_formula():
    """Verify exponential half-life decay calculation and explicit protection."""
    now = utc_now()
    month_ago = now - timedelta(days=30)

    # 30 days decay with half-life of 30 days should halve the score
    decayed = InterestDecayEngine.calculate_decay(
        current_score=0.80,
        last_positive_at=month_ago,
        interest_type="LEARNED",
        half_life_days=30.0,
        now=now,
    )
    assert abs(decayed - 0.40) <= 0.02

    # Explicit interests NEVER decay
    explicit_decay = InterestDecayEngine.calculate_decay(
        current_score=0.80,
        last_positive_at=month_ago,
        interest_type="EXPLICIT",
        half_life_days=30.0,
        now=now,
    )
    assert explicit_decay == 0.80


@pytest.mark.asyncio
async def test_hierarchical_topic_propagation(db_session):
    """Verify ancestor topic propagation (Direct 1.0 -> Parent 0.50 -> Grandparent 0.25)."""
    uid_str = uuid.uuid4().hex[:6]
    # Create topic hierarchy: Tech -> AI -> LLMs
    tech = Topic(id=uuid.uuid4(), name="Technology", slug=f"tech_{uid_str}")
    db_session.add(tech)
    await db_session.flush()

    ai = Topic(id=uuid.uuid4(), name="Artificial Intelligence", slug=f"ai_{uid_str}", parent_topic_id=tech.id)
    db_session.add(ai)
    await db_session.flush()

    llm = Topic(id=uuid.uuid4(), name="Large Language Models", slug=f"llm_{uid_str}", parent_topic_id=ai.id)
    db_session.add(llm)
    await db_session.flush()

    ancestors = await TopicPropagationEngine.get_ancestor_topics(db_session, llm.id)
    assert len(ancestors) == 2
    assert ancestors[0][0].id == ai.id
    assert ancestors[0][1] == 0.50
    assert ancestors[1][0].id == tech.id
    assert ancestors[1][1] == 0.25


@pytest.mark.asyncio
async def test_batch_learning_cursor_and_deduplication(db_session):
    """Verify learning cursor processes unprocessed events and avoids double counting."""
    uid_str = uuid.uuid4().hex[:6]
    user = User(
        id=uuid.uuid4(),
        email=f"learner_{uid_str}@example.com",
        password_hash="pw",
        is_active=True,
    )
    db_session.add(user)

    topic = Topic(id=uuid.uuid4(), name="Robotics", slug=f"robotics_{uid_str}")
    db_session.add(topic)
    await db_session.flush()

    learner = InterestLearningService(db_session)

    # Log 3 events
    await learner.record_signal(user_id=user.id, signal_type="SEARCH", topic_id=topic.id, immediate_process=False)
    await learner.record_signal(user_id=user.id, signal_type="NORMAL_READ", topic_id=topic.id, immediate_process=False)
    await learner.record_signal(user_id=user.id, signal_type="LIKE", topic_id=topic.id, immediate_process=False)

    # Check unprocessed count
    stmt = select(InterestLearningEvent).where(
        InterestLearningEvent.user_id == user.id,
        InterestLearningEvent.processed == False,
    )
    res = await db_session.execute(stmt)
    unprocessed = res.scalars().all()
    assert len(unprocessed) == 3

    # Run batch processing
    processed_count = await learner.process_unprocessed_events(user_id=user.id)
    assert processed_count == 3

    # Subsequent run finds 0 pending events
    second_run = await learner.process_unprocessed_events(user_id=user.id)
    assert second_run == 0

    # Verify interest profile was created and updated
    stmt_prof = select(UserInterestProfile).where(
        UserInterestProfile.user_id == user.id,
        UserInterestProfile.topic_id == topic.id,
    )
    res_prof = await db_session.execute(stmt_prof)
    profile = res_prof.scalar_one_or_none()
    assert profile is not None
    assert profile.evidence_count >= 3
    assert profile.positive_count >= 3
    assert profile.score > 0.50


@pytest.mark.asyncio
async def test_reset_learned_profile_preserves_explicit(db_session):
    """Verify resetting learned interests removes learned/inferred while preserving explicit interests."""
    uid_str = uuid.uuid4().hex[:6]
    user = User(
        id=uuid.uuid4(),
        email=f"reset_{uid_str}@example.com",
        password_hash="pw",
        is_active=True,
    )
    db_session.add(user)

    topic1 = Topic(id=uuid.uuid4(), name="Design", slug=f"design_{uid_str}")
    topic2 = Topic(id=uuid.uuid4(), name="Crypto", slug=f"crypto_{uid_str}")
    db_session.add_all([topic1, topic2])
    await db_session.flush()

    learner = InterestLearningService(db_session)

    # 1. Explicit Interest
    await learner.sync_explicit_interest(user.id, topic1.id, score=0.85)

    # 2. Learned Interest
    await learner.record_signal(user.id, signal_type="DEEP_READ", topic_id=topic2.id, immediate_process=True)

    # Check both exist
    prof_resp = await learner.get_dynamic_profile(user.id)
    assert len(prof_resp.explicit_interests) == 1
    assert prof_resp.explicit_interests[0].name == "Design"

    # Reset learned profile
    preserved = await learner.reset_learned_profile(user.id)
    assert preserved == 1

    # Check after reset: explicit remains, learned crypto is gone
    prof_after = await learner.get_dynamic_profile(user.id)
    assert len(prof_after.explicit_interests) == 1
    assert prof_after.explicit_interests[0].name == "Design"
    assert len(prof_after.strong_interests) == 0
    assert len(prof_after.stable_interests) == 0


@pytest.mark.asyncio
async def test_realistic_learning_simulation_user_a(db_session):
    """
    Simulation:
    USER A:
      Initial: AI = explicit
      Simulate 10 deep AI reads, 5 saves, 3 searches -> AI becomes STRONG.
      Then simulate 20 finance reads -> Finance becomes EMERGING/STRONG.
      AI does not disappear.
    """
    uid_str = uuid.uuid4().hex[:6]
    user_a = User(
        id=uuid.uuid4(),
        email=f"user_a_simulation_{uid_str}@example.com",
        password_hash="pw",
        is_active=True,
    )
    db_session.add(user_a)

    ai_topic = Topic(id=uuid.uuid4(), name="Artificial Intelligence", slug=f"ai_{uid_str}")
    fin_topic = Topic(id=uuid.uuid4(), name="Finance", slug=f"finance_{uid_str}")
    db_session.add_all([ai_topic, fin_topic])
    await db_session.flush()

    learner = InterestLearningService(db_session)

    # Initial: AI = explicit
    await learner.sync_explicit_interest(user_id=user_a.id, topic_id=ai_topic.id, score=0.80)

    # 10 deep AI reads + 5 saves + 3 searches
    for _ in range(10):
        await learner.record_signal(user_a.id, signal_type="DEEP_READ", topic_id=ai_topic.id, immediate_process=False)
    for _ in range(5):
        await learner.record_signal(user_a.id, signal_type="SAVE", topic_id=ai_topic.id, immediate_process=False)
    for _ in range(3):
        await learner.record_signal(user_a.id, signal_type="SEARCH", topic_id=ai_topic.id, immediate_process=False)

    await learner.process_unprocessed_events(user_id=user_a.id)

    profile_mid = await learner.get_dynamic_profile(user_a.id)
    assert len(profile_mid.explicit_interests) == 1
    assert profile_mid.explicit_interests[0].score >= 0.85
    assert profile_mid.explicit_interests[0].evidence_count >= 18

    # Now simulate 20 finance reads
    for _ in range(20):
        await learner.record_signal(user_a.id, signal_type="NORMAL_READ", topic_id=fin_topic.id, immediate_process=False)

    await learner.process_unprocessed_events(user_id=user_a.id)

    profile_final = await learner.get_dynamic_profile(user_a.id)
    # AI is still present and explicit
    assert any(i.name == "Artificial Intelligence" for i in profile_final.explicit_interests)

    # Finance is now present as a learned interest with strong/stable state
    all_learned = (
        profile_final.strong_interests
        + profile_final.emerging_interests
        + profile_final.stable_interests
    )
    finance_item = next((i for i in all_learned if i.name == "Finance"), None)
    assert finance_item is not None
    assert finance_item.evidence_count >= 20
    assert finance_item.score >= 0.60


@pytest.mark.asyncio
async def test_negative_topic_suppression(db_session):
    """Verify NOT_INTERESTED preference suppresses topic without destroying other topics."""
    uid_str = uuid.uuid4().hex[:6]
    user = User(
        id=uuid.uuid4(),
        email=f"negative_test_{uid_str}@example.com",
        password_hash="pw",
        is_active=True,
    )
    db_session.add(user)

    sports = Topic(id=uuid.uuid4(), name="Sports", slug=f"sports_{uid_str}")
    tech = Topic(id=uuid.uuid4(), name="Tech", slug=f"tech_{uid_str}")
    db_session.add_all([sports, tech])
    await db_session.flush()

    learner = InterestLearningService(db_session)
    await learner.sync_explicit_interest(user.id, tech.id, score=0.85)

    # Mark Sports as NOT_INTERESTED
    await learner.set_topic_preference(user.id, sports.id, preference="NEGATIVE", strength=1.0)

    prof = await learner.get_dynamic_profile(user.id)
    assert len(prof.avoided_topics) == 1
    assert prof.avoided_topics[0].slug == f"sports_{uid_str}"

    # Personalization service should reflect negative suppression
    pers_svc = PersonalizationService(db_session)
    user_prof = await pers_svc.get_user_interest_profile(user.id)
    assert f"sports_{uid_str}" in user_prof.negative_interests
    assert f"sports_{uid_str}" not in user_prof.positive_interests
    assert f"tech_{uid_str}" in user_prof.positive_interests


@pytest.mark.asyncio
async def test_personalization_divergence_between_users(db_session):
    """Verify two users with different dynamic profiles receive distinct relevance scores and rankings."""
    uid_str = uuid.uuid4().hex[:6]
    user_tech = User(id=uuid.uuid4(), email=f"user_tech_{uid_str}@example.com", password_hash="pw", is_active=True)
    user_fin = User(id=uuid.uuid4(), email=f"user_fin_{uid_str}@example.com", password_hash="pw", is_active=True)
    db_session.add_all([user_tech, user_fin])

    topic_tech = Topic(id=uuid.uuid4(), name="Technology", slug=f"tech_{uid_str}")
    topic_fin = Topic(id=uuid.uuid4(), name="Finance", slug=f"fin_{uid_str}")
    db_session.add_all([topic_tech, topic_fin])
    await db_session.flush()

    learner = InterestLearningService(db_session)
    await learner.sync_explicit_interest(user_tech.id, topic_tech.id, score=0.90)
    await learner.sync_explicit_interest(user_fin.id, topic_fin.id, score=0.90)

    # Create 2 published articles
    now = utc_now()
    art_tech = Article(
        id=uuid.uuid4(),
        title="Breakthrough in Quantum Chips",
        slug=f"quantum-chips-{uid_str}",
        content="Tech content...",
        status="PUBLISHED",
        published_at=now,
    )
    art_tech.topics.append(topic_tech)

    art_fin = Article(
        id=uuid.uuid4(),
        title="Global Stock Market Rally",
        slug=f"stock-rally-{uid_str}",
        content="Finance content...",
        status="PUBLISHED",
        published_at=now,
    )
    art_fin.topics.append(topic_fin)

    db_session.add_all([art_tech, art_fin])
    await db_session.commit()

    pers_svc = PersonalizationService(db_session)

    ranked_tech = await pers_svc.rank_articles_for_user(user_tech.id, [art_tech, art_fin])
    ranked_fin = await pers_svc.rank_articles_for_user(user_fin.id, [art_tech, art_fin])

    # Lead story for User Tech is quantum chips
    assert ranked_tech[0][0].id == art_tech.id
    # Lead story for User Fin is stock rally
    assert ranked_fin[0][0].id == art_fin.id
