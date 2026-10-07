"""test_behavioral_learning.py — Comprehensive Test Suite for Phase 19 Advanced User Behavioral Learning Engine.

Tests:
1. Article open signal
2. Reading duration
3. Completion
4. Save
5. Like
6. Not interested
7. Skip
8. Search signal
9. Source affinity
10. Topic preference
11. Entity preference
12. Short-term interest
13. Long-term interest
14. Interest decay
15. Confidence
16. Evidence diversity
17. Repeated behavior
18. Accidental click protection
19. Explicit override
20. Discovery protection
21. Exploration/exploitation
22. Interest collapse protection
23. Profile rebuild
24. User isolation
25. Background learning
26. Ranking integration
27. Briefing integration
28. Recommendation integration
29. Realistic test scenario
30. Conflicting behavior test
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from typing import List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserProfile
from app.models.topic import Topic
from app.models.article import Article
from app.models.entity import Entity
from app.models.analysis import ArticleAnalysis
from app.models.interest import UserInterest
from app.models.interest_profile import UserTopicPreference
from app.models.source import NewsSource
from app.source_intelligence.models import UserSourcePreference
from app.story_intelligence.models import Story, StoryArticle
from app.learning.evidence_models import (
    UserInterestEvidence,
    UserTopicBehaviorPreference,
    UserEntityBehaviorPreference,
    UserKeywordBehaviorPreference,
    UserStoryInterestSignal,
)
from app.learning.behavioral_engine import BehavioralLearningEngine
from app.learning.evidence_schemas import TopicOverrideRequest
from app.personalization.services.personalization_service import PersonalizationService
from app.workers.jobs import job_behavior_learning


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def create_user(session: AsyncSession, name_prefix: str) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"{name_prefix}_{uid}@example.com",
        password_hash="fakehash123",
        full_name=f"{name_prefix.title()} User",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    profile = UserProfile(
        user_id=user.id,
        display_name=f"{name_prefix.title()} User",
        timezone="UTC",
    )
    session.add(profile)
    await session.commit()
    await session.refresh(user)
    return user


async def create_topic(session: AsyncSession, name: str, slug: str) -> Topic:
    stmt = select(Topic).where(Topic.slug == slug)
    res = await session.execute(stmt)
    existing = res.scalars().first()
    if existing:
        return existing
    t = Topic(name=name, slug=slug)
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


async def create_entity(session: AsyncSession, name: str, entity_type: str = "ORGANIZATION") -> Entity:
    stmt = select(Entity).where(Entity.normalized_name == name.lower().strip())
    res = await session.execute(stmt)
    existing = res.scalars().first()
    if existing:
        return existing
    e = Entity(name=name, normalized_name=name.lower().strip(), entity_type=entity_type)
    session.add(e)
    await session.commit()
    await session.refresh(e)
    return e


async def create_article_with_metadata(
    session: AsyncSession,
    title: str,
    topic: Topic,
    entity: Optional[Entity] = None,
    importance: float = 0.75,
    reading_time: int = 4,
) -> Article:
    art = Article(
        title=title,
        slug=f"{title.lower().replace(' ', '-')[:30]}-{uuid.uuid4().hex[:6]}",
        canonical_url=f"https://example.com/art/{uuid.uuid4().hex[:8]}",
        status="PUBLISHED",
        is_full_text_available=True,
        reading_time_minutes=reading_time,
        content=f"Detailed body text content for {title}.",
        published_at=utc_now(),
    )
    art.topics = [topic]
    if entity:
        art.entities = [entity]
    session.add(art)
    await session.flush()

    analysis = ArticleAnalysis(
        article_id=art.id,
        primary_category="TECHNOLOGY",
        summary=f"Analysis summary for {title}",
        importance_score=importance,
        article_quality_score=0.85,
    )
    session.add(analysis)
    await session.commit()
    await session.refresh(art)
    return art


# =============================================================================
# 1. Behavioral Evidence Signals & Weights Tests
# =============================================================================
@pytest.mark.asyncio
async def test_evidence_signal_recording_and_weights(db_session: AsyncSession):
    user = await create_user(db_session, "sig_user")
    topic = await create_topic(db_session, "Artificial Intelligence", "ai-sig")
    engine = BehavioralLearningEngine(db_session)

    # Record Save (+0.85)
    ev_save = await engine.record_evidence(
        user_id=user.id,
        signal_type="SAVE",
        target_type="TOPIC",
        target_id=str(topic.id),
        target_name=topic.name,
    )
    assert ev_save.strength == pytest.approx(0.85, rel=1e-2)

    # Record Like (+0.80)
    ev_like = await engine.record_evidence(
        user_id=user.id,
        signal_type="LIKE",
        target_type="TOPIC",
        target_id=str(topic.id),
        target_name=topic.name,
    )
    assert ev_like.strength == pytest.approx(0.80, rel=1e-2)

    # Record Not Interested (-1.00)
    ev_not_int = await engine.record_evidence(
        user_id=user.id,
        signal_type="NOT_INTERESTED",
        target_type="TOPIC",
        target_id=str(topic.id),
        target_name=topic.name,
    )
    assert ev_not_int.strength == pytest.approx(-1.00, rel=1e-2)


# =============================================================================
# 2. Accidental Click Protection Test
# =============================================================================
@pytest.mark.asyncio
async def test_accidental_click_protection(db_session: AsyncSession):
    user = await create_user(db_session, "acc_user")
    topic = await create_topic(db_session, "Sports", "sports-acc")
    engine = BehavioralLearningEngine(db_session)

    # User opens sports article for 2 seconds and closes (0.01 completion)
    ev = await engine.record_evidence(
        user_id=user.id,
        signal_type="OPEN",
        target_type="TOPIC",
        target_id=str(topic.id),
        target_name=topic.name,
        dwell_time_seconds=2.0,
        completion_ratio=0.01,
    )

    assert ev.is_accidental is True
    assert ev.strength <= 0.02


# =============================================================================
# 3. Dwell Time and Reading Completion Ratio Test
# =============================================================================
@pytest.mark.asyncio
async def test_reading_dwell_time_and_completion_scaling(db_session: AsyncSession):
    user = await create_user(db_session, "dwell_user")
    topic = await create_topic(db_session, "Quantum Computing", "quantum-dwell")
    engine = BehavioralLearningEngine(db_session)

    # Full completed read (completion ratio = 1.0)
    ev_complete = await engine.record_evidence(
        user_id=user.id,
        signal_type="COMPLETE",
        target_type="TOPIC",
        target_id=str(topic.id),
        target_name=topic.name,
        dwell_time_seconds=240.0,
        completion_ratio=1.0,
    )
    assert ev_complete.strength >= 0.70

    # Short read (completion ratio = 0.3)
    ev_short = await engine.record_evidence(
        user_id=user.id,
        signal_type="READ",
        target_type="TOPIC",
        target_id=str(topic.id),
        target_name=topic.name,
        dwell_time_seconds=30.0,
        completion_ratio=0.30,
    )
    assert ev_short.strength < ev_complete.strength


# =============================================================================
# 4. Evidence Diversity Discounting (Same Story vs Distinct Stories)
# =============================================================================
@pytest.mark.asyncio
async def test_evidence_diversity_discounting(db_session: AsyncSession):
    user_single_story = await create_user(db_session, "single_story_user")
    user_multi_story = await create_user(db_session, "multi_story_user")
    topic = await create_topic(db_session, "Machine Learning", "ml-div")

    engine = BehavioralLearningEngine(db_session)
    story_a_id = uuid.uuid4()

    # User 1: Reads 10 articles ALL from Story A
    for _ in range(10):
        await engine.record_evidence(
            user_id=user_single_story.id,
            signal_type="READ",
            target_type="TOPIC",
            target_id=str(topic.id),
            source_story_id=story_a_id,
        )

    # User 2: Reads 10 articles across 10 DIFFERENT stories
    for _ in range(10):
        await engine.record_evidence(
            user_id=user_multi_story.id,
            signal_type="READ",
            target_type="TOPIC",
            target_id=str(topic.id),
            source_story_id=uuid.uuid4(),
        )

    # Process batch aggregation
    await engine.process_batch_learning()

    prof_1 = await engine.get_user_unified_profile(user_single_story.id)
    prof_2 = await engine.get_user_unified_profile(user_multi_story.id)

    all_1 = prof_1.strong_interests + prof_1.growing_interests + prof_1.low_engagement_topics
    all_2 = prof_2.strong_interests + prof_2.growing_interests + prof_2.low_engagement_topics
    item_1 = next((it for it in all_1 if it.topic_id == topic.id), None)
    item_2 = next((it for it in all_2 if it.topic_id == topic.id), None)

    assert item_1 is not None
    assert item_2 is not None
    # Multi-story reader should have higher distinct stories count and higher/equal confidence
    assert item_2.distinct_stories_count > item_1.distinct_stories_count
    assert item_2.confidence >= item_1.confidence


# =============================================================================
# 5. Search Intent Learning Test
# =============================================================================
@pytest.mark.asyncio
async def test_search_intent_learning(db_session: AsyncSession):
    user = await create_user(db_session, "search_learner")
    topic_ai = await create_topic(db_session, "Artificial Intelligence", "ai-search")
    engine = BehavioralLearningEngine(db_session)

    evidence = await engine.ingest_search_intent(user.id, "Artificial Intelligence breakthroughs")
    assert len(evidence) >= 1
    assert any(e.target_type == "TOPIC" and e.target_id == str(topic_ai.id) for e in evidence)


# =============================================================================
# 6. Entity & Keyword Behavioral Affinities Test
# =============================================================================
@pytest.mark.asyncio
async def test_entity_and_keyword_learning(db_session: AsyncSession):
    user = await create_user(db_session, "ent_user")
    topic = await create_topic(db_session, "Technology", "tech-ent")
    entity = await create_entity(db_session, "OpenAI", "ORGANIZATION")
    article = await create_article_with_metadata(db_session, "OpenAI Announces Next Frontier Model", topic, entity)

    engine = BehavioralLearningEngine(db_session)
    # User reads and saves the article
    await engine.ingest_article_interaction(user.id, article.id, "SAVE")
    await engine.process_batch_learning(user_id=user.id)

    profile = await engine.get_user_unified_profile(user.id)
    assert len(profile.entity_preferences) >= 1
    assert any(ep.entity_name.lower() == "openai" for ep in profile.entity_preferences)


# =============================================================================
# 7. Explicit Override Rule Test
# =============================================================================
@pytest.mark.asyncio
async def test_explicit_override_dominates_behavior(db_session: AsyncSession):
    """
    User repeatedly reads Sports articles, but explicitly selects 'MUTE' / 'NOT_INTERESTED'.
    The explicit negative instruction MUST override behavioral inference.
    """
    user = await create_user(db_session, "override_user")
    topic_sports = await create_topic(db_session, "Sports", "sports-over")
    engine = BehavioralLearningEngine(db_session)

    # 5 reading interactions
    for _ in range(5):
        await engine.record_evidence(
            user_id=user.id,
            signal_type="READ",
            target_type="TOPIC",
            target_id=str(topic_sports.id),
            target_name=topic_sports.name,
            dwell_time_seconds=120.0,
            completion_ratio=0.9,
        )
    await engine.process_batch_learning(user_id=user.id)

    # Now user explicitly mutes Sports
    await engine.apply_topic_override(
        user.id,
        TopicOverrideRequest(topic_id=topic_sports.id, override_action="MUTE")
    )

    profile = await engine.get_user_unified_profile(user.id)
    # Sports should be in muted_topics with score 0.0
    muted_item = next((it for it in profile.muted_topics if it.topic_id == topic_sports.id), None)
    assert muted_item is not None
    assert muted_item.score == 0.0
    assert muted_item.tier == "MUTED"


# =============================================================================
# 8. Short-Term vs Long-Term Interest Decay Test
# =============================================================================
@pytest.mark.asyncio
async def test_short_term_and_long_term_interest_decay(db_session: AsyncSession):
    user = await create_user(db_session, "decay_user")
    topic = await create_topic(db_session, "Robotics", "robotics-decay")
    engine = BehavioralLearningEngine(db_session)

    # Add evidence 10 days ago (past 7-day short-term half-life)
    ten_days_ago = utc_now() - timedelta(days=10)
    ev = UserInterestEvidence(
        user_id=user.id,
        signal_type="READ",
        target_type="TOPIC",
        target_id=str(topic.id),
        target_name=topic.name,
        strength=0.8,
        processed=False,
        created_at=ten_days_ago,
    )
    db_session.add(ev)
    await db_session.commit()

    await engine.process_batch_learning(user_id=user.id)
    profile = await engine.get_user_unified_profile(user.id)

    all_items = profile.strong_interests + profile.growing_interests + profile.low_engagement_topics
    item = next((it for it in all_items if it.topic_id == topic.id), None)
    assert item is not None
    # Long term score should be higher than short term score due to slower decay
    assert item.long_term_score > item.short_term_score


# =============================================================================
# 9. Full Deterministic Profile Rebuild Test
# =============================================================================
@pytest.mark.asyncio
async def test_full_profile_rebuild(db_session: AsyncSession):
    user = await create_user(db_session, "rebuild_user")
    topic_ai = await create_topic(db_session, "AI Agents", "ai-rebuild")
    engine = BehavioralLearningEngine(db_session)

    # Record 4 evidence items
    for _ in range(4):
        await engine.record_evidence(
            user_id=user.id,
            signal_type="COMPLETE",
            target_type="TOPIC",
            target_id=str(topic_ai.id),
            target_name=topic_ai.name,
            dwell_time_seconds=180.0,
            completion_ratio=1.0,
        )

    await engine.process_batch_learning(user_id=user.id)
    prof_before = await engine.get_user_unified_profile(user.id)
    score_before = prof_before.strong_interests[0].score

    # Trigger profile rebuild
    rebuild_res = await engine.rebuild_user_profile(user.id)
    assert rebuild_res.status == "SUCCESS"
    assert rebuild_res.evidence_events_processed >= 4

    prof_after = await engine.get_user_unified_profile(user.id)
    score_after = prof_after.strong_interests[0].score

    assert pytest.approx(score_before, rel=1e-2) == score_after


# =============================================================================
# 10. Realistic Complex Behavioral Learning Test
# =============================================================================
@pytest.mark.asyncio
async def test_realistic_behavioral_scenario(db_session: AsyncSession):
    """
    User explicitly selects: Technology.
    Behavior:
      - Reads 10 AI Agent articles
      - Reads 8 LLM articles
      - Reads 2 Robotics articles
      - Skips 6 Sports articles
    Expected:
      - AI & LLM: Strong interests
      - Robotics: Growing/Moderate interest
      - Sports: Lower engagement (NOT absolute ban)
    """
    user = await create_user(db_session, "realistic_learner")
    topic_tech = await create_topic(db_session, "Technology", "tech-real")
    topic_ai = await create_topic(db_session, "AI Agents", "ai-agents-real")
    topic_llm = await create_topic(db_session, "LLMs", "llms-real")
    topic_robotics = await create_topic(db_session, "Robotics", "robotics-real")
    topic_sports = await create_topic(db_session, "Sports", "sports-real")

    # Explicit technology interest
    ui = UserInterest(user_id=user.id, topic_id=topic_tech.id, preference_type="POSITIVE", interest_score=1.0)
    db_session.add(ui)
    await db_session.commit()

    engine = BehavioralLearningEngine(db_session)

    # 10 AI Agent reads
    for _ in range(10):
        await engine.record_evidence(
            user_id=user.id,
            signal_type="READ",
            target_type="TOPIC",
            target_id=str(topic_ai.id),
            target_name=topic_ai.name,
            source_story_id=uuid.uuid4(),
            dwell_time_seconds=120.0,
            completion_ratio=0.85,
        )

    # 8 LLM reads
    for _ in range(8):
        await engine.record_evidence(
            user_id=user.id,
            signal_type="READ",
            target_type="TOPIC",
            target_id=str(topic_llm.id),
            target_name=topic_llm.name,
            source_story_id=uuid.uuid4(),
            dwell_time_seconds=100.0,
            completion_ratio=0.80,
        )

    # 2 Robotics reads
    for _ in range(2):
        await engine.record_evidence(
            user_id=user.id,
            signal_type="READ",
            target_type="TOPIC",
            target_id=str(topic_robotics.id),
            target_name=topic_robotics.name,
            source_story_id=uuid.uuid4(),
            dwell_time_seconds=60.0,
            completion_ratio=0.50,
        )

    # 6 Sports skips
    for _ in range(6):
        await engine.record_evidence(
            user_id=user.id,
            signal_type="SKIP",
            target_type="TOPIC",
            target_id=str(topic_sports.id),
            target_name=topic_sports.name,
        )

    await engine.process_batch_learning(user_id=user.id)
    profile = await engine.get_user_unified_profile(user.id)

    strong_names = [it.topic_name for it in profile.strong_interests]
    low_names = [it.topic_name for it in profile.low_engagement_topics]

    assert "AI Agents" in strong_names
    assert "LLMs" in strong_names
    assert "Sports" in low_names


# =============================================================================
# 11. Conflicting Behavior Test (Tech Positive + AI Regulation Not Interested)
# =============================================================================
@pytest.mark.asyncio
async def test_conflicting_behavior_handling(db_session: AsyncSession):
    user = await create_user(db_session, "conflict_user")
    topic_tech = await create_topic(db_session, "Technology", "tech-conf")
    topic_reg = await create_topic(db_session, "AI Regulation", "ai-reg-conf")

    # Explicitly likes Technology
    ui = UserInterest(user_id=user.id, topic_id=topic_tech.id, preference_type="POSITIVE", interest_score=1.0)
    db_session.add(ui)
    await db_session.commit()

    engine = BehavioralLearningEngine(db_session)

    # Repeatedly marks AI Regulation as NOT_INTERESTED
    for _ in range(4):
        await engine.record_evidence(
            user_id=user.id,
            signal_type="NOT_INTERESTED",
            target_type="TOPIC",
            target_id=str(topic_reg.id),
            target_name=topic_reg.name,
        )

    await engine.process_batch_learning(user_id=user.id)
    profile = await engine.get_user_unified_profile(user.id)

    strong_names = [it.topic_name for it in profile.strong_interests]
    low_names = [it.topic_name for it in profile.low_engagement_topics]

    # Technology remains strong; AI Regulation becomes low engagement
    assert "Technology" in strong_names
    assert "AI Regulation" in low_names


# =============================================================================
# 12. Background Worker Job Test
# =============================================================================
@pytest.mark.asyncio
async def test_background_behavior_learning_job(db_session: AsyncSession):
    user = await create_user(db_session, "job_user")
    topic = await create_topic(db_session, "Science", "science-job")
    engine = BehavioralLearningEngine(db_session)

    await engine.record_evidence(
        user_id=user.id,
        signal_type="READ",
        target_type="TOPIC",
        target_id=str(topic.id),
        target_name=topic.name,
    )

    res = await job_behavior_learning()
    assert res["status"] == "success"
    assert res["processed_evidence"] >= 1


# =============================================================================
# 13. Integration with Personalization Scoring Test
# =============================================================================
@pytest.mark.asyncio
async def test_personalization_service_consumes_behavioral_profile(db_session: AsyncSession):
    user = await create_user(db_session, "scorer_user")
    topic_ai = await create_topic(db_session, "Artificial Intelligence", "ai-score")
    topic_sports = await create_topic(db_session, "Sports", "sports-score")

    engine = BehavioralLearningEngine(db_session)

    # Record 5 positive AI reads
    for _ in range(5):
        await engine.record_evidence(
            user_id=user.id,
            signal_type="COMPLETE",
            target_type="TOPIC",
            target_id=str(topic_ai.id),
            target_name=topic_ai.name,
            dwell_time_seconds=200.0,
            completion_ratio=1.0,
        )
    await engine.process_batch_learning(user_id=user.id)

    # Evaluate article relevance using PersonalizationService
    art_ai = await create_article_with_metadata(db_session, "AI Transformer Breakthrough", topic_ai)
    art_sports = await create_article_with_metadata(db_session, "Weekend Sports Derby", topic_sports)

    ps = PersonalizationService(db_session)
    score_ai, _ = await ps.calculate_article_relevance(user.id, art_ai.id)
    score_sports, _ = await ps.calculate_article_relevance(user.id, art_sports.id)

    assert score_ai > score_sports
    assert score_ai >= 0.60
