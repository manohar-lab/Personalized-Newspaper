"""test_briefings.py — Comprehensive Test Suite for Phase 18 Personal News Briefing Engine."""
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User, UserProfile
from app.models.topic import Topic
from app.models.interest import UserInterest
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.models.reading_history import ReadingHistory
from app.story_intelligence.models import Story, StoryArticle
from app.briefings.models import (
    BriefingStatus,
    BriefingType,
    Daypart,
    NewsBriefing,
    NewsBriefingItem,
    NewsSession,
)
from app.briefings.engine import PersonalNewsBriefingEngine
from app.briefings.change_detector import ChangeDetector
from app.briefings.briefing_selector import BriefingSelector
from app.briefings.session_service import NewsSessionService
from app.editorial.schemas import EditorialCandidate
from app.workers.jobs import briefing_generation_job


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def create_user(session: AsyncSession, name_prefix: str, tz: str = "UTC") -> User:
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        email=f"{name_prefix}_{unique_id}@example.com",
        password_hash="fakehash123",
        full_name=f"{name_prefix.title()} User",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    profile = UserProfile(
        user_id=user.id,
        display_name=f"{name_prefix.title()} User",
        timezone=tz,
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


async def add_interest(session: AsyncSession, user_id: uuid.UUID, topic_id: uuid.UUID, score: float = 1.0):
    ui = UserInterest(
        user_id=user_id,
        topic_id=topic_id,
        interest_score=score,
        preference_type="POSITIVE",
        source="EXPLICIT",
    )
    session.add(ui)
    await session.commit()


async def create_story_with_articles(
    session: AsyncSession,
    title: str,
    category: str,
    topic: Topic,
    importance: float = 0.70,
    quality: float = 0.80,
    source_count: int = 3,
    indep_count: int = 3,
    is_developing: bool = False,
    published_hours_ago: float = 2.0,
) -> Story:
    now = utc_now()
    pub_time = now - timedelta(hours=published_hours_ago)

    st = Story(
        title=title,
        slug=f"{title.lower().replace(' ', '-')[:30]}-{uuid.uuid4().hex[:6]}",
        summary=f"Summary of {title} covering recent developments.",
        importance_score=importance,
        quality_score=quality,
        activity_score=0.75,
        status="DEVELOPING" if is_developing else "STABLE",
        first_published_at=pub_time,
        last_updated_at=now,
        article_count=source_count,
        source_count=source_count,
        independent_source_count=indep_count,
        primary_topic_id=topic.id,
    )
    session.add(st)
    await session.flush()

    art = Article(
        title=f"{title} - Main Report",
        slug=f"art-{uuid.uuid4().hex[:8]}",
        canonical_url=f"https://example.com/news/{uuid.uuid4().hex[:8]}",
        status="PUBLISHED",
        is_full_text_available=True,
        content=f"Detailed body text content for {title}. Comprehensive reporting on the latest news events.",
        published_at=pub_time,
    )
    art.topics = [topic]
    session.add(art)
    await session.flush()

    analysis = ArticleAnalysis(
        article_id=art.id,
        primary_category=category,
        summary=f"Analysis summary for {title}",
        importance_score=importance,
        article_quality_score=quality,
    )
    session.add(analysis)

    sa = StoryArticle(
        story_id=st.id,
        article_id=art.id,
        relationship_type="PRIMARY",
        similarity_score=0.95,
    )
    session.add(sa)
    st.primary_article_id = art.id
    st.latest_article_id = art.id
    session.add(st)
    await session.commit()
    await session.refresh(st)
    return st


# =============================================================================
# 1. New Story Detection Test
# =============================================================================
@pytest.mark.asyncio
async def test_new_story_detection(db_session: AsyncSession):
    user = await create_user(db_session, "new_detector")
    detector = ChangeDetector(db_session)

    last_visit = utc_now() - timedelta(hours=8)
    new_pub_time = utc_now() - timedelta(hours=2)

    cand = EditorialCandidate(
        story_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        title="Brand New Overnight Breakthrough",
        summary="A new discovery was announced overnight.",
        published_at=new_pub_time,
        importance_score=0.70,
        personal_relevance_score=0.60,
        topics=["Science"],
        is_read=False,
    )

    b_type, update_score, reason = detector.evaluate_candidate_change(cand, last_visit)
    assert b_type == BriefingType.NEW.value
    assert "New development" in reason or "since your last visit" in reason


# =============================================================================
# 2. Updated Story Detection & Meaningful Update Score Test
# =============================================================================
@pytest.mark.asyncio
async def test_updated_story_detection(db_session: AsyncSession):
    user = await create_user(db_session, "update_detector")
    detector = ChangeDetector(db_session)

    last_visit = utc_now() - timedelta(hours=12)

    # Multi-source developing story with 4 independent sources
    cand = EditorialCandidate(
        story_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        title="Developing Economic Policy Shift",
        summary="Regulators released new comprehensive frameworks.",
        published_at=utc_now() - timedelta(hours=18),
        importance_score=0.82,
        personal_relevance_score=0.55,
        source_count=5,
        independent_source_count=4,
        is_developing=True,
        story_article_count=5,
        topics=["Economy"],
        is_read=False,
    )

    b_type, update_score, reason = detector.evaluate_candidate_change(cand, last_visit)
    assert b_type in (BriefingType.UPDATED.value, BriefingType.IMPORTANT.value)
    assert update_score >= 0.50
    assert cand.independent_source_count >= 3


# =============================================================================
# 3. Follow-Up Story Detection Test
# =============================================================================
@pytest.mark.asyncio
async def test_follow_up_detection(db_session: AsyncSession):
    user = await create_user(db_session, "followup_user")
    detector = ChangeDetector(db_session)

    last_visit = utc_now() - timedelta(hours=24)

    # Story user previously read, now has a meaningful update
    cand = EditorialCandidate(
        story_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        title="AI Company Releases Specifications",
        summary="Full open benchmarks and weights released.",
        published_at=utc_now() - timedelta(hours=30),
        importance_score=0.80,
        personal_relevance_score=0.90,
        topics=["Artificial Intelligence"],
        is_read=True,
        user_read_percentage=1.0,
        has_meaningful_update=True,
    )

    b_type, update_score, reason = detector.evaluate_candidate_change(cand, last_visit)
    assert b_type == BriefingType.FOLLOW_UP.value
    assert "Follow-up" in reason


# =============================================================================
# 4. Important Stories Selection Test (Broad Significance Outside User Interests)
# =============================================================================
@pytest.mark.asyncio
async def test_important_story_selection_outside_interests(db_session: AsyncSession):
    user = await create_user(db_session, "niche_user")
    detector = ChangeDetector(db_session)

    last_visit = utc_now() - timedelta(hours=10)

    # Major global election / earthquake story (low personal relevance, very high importance)
    cand = EditorialCandidate(
        story_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        title="Major National Election Results Finalized",
        summary="Election commission certifies official tally.",
        published_at=utc_now() - timedelta(hours=3),
        importance_score=0.95,
        personal_relevance_score=0.20,
        source_count=6,
        independent_source_count=5,
        topics=["Politics"],
        is_read=False,
    )

    b_type, update_score, reason = detector.evaluate_candidate_change(
        cand, last_visit, user_top_topics=["Gaming", "Anime"]
    )
    assert b_type == BriefingType.IMPORTANT.value
    assert "broad significance" in reason.lower() or "major" in reason.lower()


# =============================================================================
# 5. News Session Tracking & Lifecycle Test
# =============================================================================
@pytest.mark.asyncio
async def test_session_tracking_lifecycle(db_session: AsyncSession):
    user = await create_user(db_session, "session_user")
    service = NewsSessionService(db_session)

    # 1. Start session
    sess = await service.start_session(user.id)
    assert sess.id is not None
    assert sess.user_id == user.id
    assert sess.meaningful_activity is False

    # 2. Heartbeat with interactions
    updated_sess = await service.record_heartbeat(
        session_id=sess.id,
        user_id=user.id,
        stories_viewed_delta=3,
        articles_opened_delta=1,
    )
    assert updated_sess.stories_viewed == 3
    assert updated_sess.articles_opened == 1
    assert updated_sess.meaningful_activity is True

    # 3. End session
    ended_sess = await service.end_session(sess.id, user.id)
    assert ended_sess.ended_at is not None

    # 4. Query last meaningful session baseline
    last_baseline = await service.get_last_meaningful_session_time(user.id)
    assert last_baseline is not None
    assert isinstance(last_baseline, datetime)


# =============================================================================
# 6. Full Briefing Generation & Persistence Test
# =============================================================================
@pytest.mark.asyncio
async def test_briefing_generation_and_persistence(db_session: AsyncSession):
    user = await create_user(db_session, "briefing_gen")
    topic_tech = await create_topic(db_session, "Technology", "tech-gen")
    topic_world = await create_topic(db_session, "World", "world-gen")
    await add_interest(db_session, user.id, topic_tech.id, score=1.0)

    # Create test stories
    await create_story_with_articles(db_session, "AI Chip Breakthrough", "TECHNOLOGY", topic_tech, importance=0.85)
    await create_story_with_articles(db_session, "Global Climate Accord Signed", "WORLD", topic_world, importance=0.90)

    engine = PersonalNewsBriefingEngine(db_session)
    resp = await engine.generate_briefing(user_id=user.id, briefing_date="2026-10-07")

    assert resp is not None
    assert resp.user_id == user.id
    assert resp.briefing_date == "2026-10-07"
    assert resp.status == BriefingStatus.READY.value
    assert resp.version == 1
    assert len(resp.items) >= 2
    assert len(resp.top_items) >= 2
    assert resp.intro is not None

    # Verify DB persistence
    stmt = select(NewsBriefing).where(NewsBriefing.id == resp.id)
    persisted = (await db_session.execute(stmt)).scalars().first()
    assert persisted is not None
    assert len(persisted.items) == len(resp.items)


# =============================================================================
# 7. Briefing Size & Deduplication Limits Test
# =============================================================================
@pytest.mark.asyncio
async def test_briefing_size_and_deduplication(db_session: AsyncSession):
    detector = ChangeDetector(db_session)
    selector = BriefingSelector(detector)

    story_id = uuid.uuid4()
    candidates = []

    # 5 articles belonging to the SAME story ID
    for i in range(5):
        candidates.append(
            EditorialCandidate(
                story_id=story_id,
                article_id=uuid.uuid4(),
                title=f"Same Story Version {i}",
                summary=f"Summary version {i}",
                importance_score=0.80,
                personal_relevance_score=0.85,
                topics=["Tech"],
                is_read=False,
            )
        )

    # 10 other distinct stories
    for j in range(10):
        candidates.append(
            EditorialCandidate(
                story_id=uuid.uuid4(),
                article_id=uuid.uuid4(),
                title=f"Distinct Story {j}",
                summary=f"Summary distinct {j}",
                importance_score=0.70,
                personal_relevance_score=0.60,
                topics=[f"Topic{j % 4}"],
                is_read=False,
            )
        )

    top, changed, all_items, caught_up, intro = selector.select_briefing_items(
        candidates=candidates,
        last_session_at=utc_now() - timedelta(hours=24),
        max_items=7,
        min_items=3,
    )

    # Size should never exceed 7
    assert len(all_items) <= 7
    # Story-level deduplication: only 1 item for story_id
    matched_story_items = [it for it in all_items if it.candidate.story_id == story_id]
    assert len(matched_story_items) == 1


# =============================================================================
# 8. Topic and Source Diversity Test
# =============================================================================
@pytest.mark.asyncio
async def test_topic_and_source_diversity(db_session: AsyncSession):
    detector = ChangeDetector(db_session)
    selector = BriefingSelector(detector)

    candidates = []
    # 8 AI stories from "TechWire"
    for i in range(8):
        candidates.append(
            EditorialCandidate(
                story_id=uuid.uuid4(),
                article_id=uuid.uuid4(),
                title=f"AI Story {i}",
                summary="AI announcement.",
                source_name="TechWire",
                importance_score=0.70,
                personal_relevance_score=0.90,
                topics=["AI"],
                is_read=False,
            )
        )

    # 2 Business stories from "Financial Times"
    for j in range(2):
        candidates.append(
            EditorialCandidate(
                story_id=uuid.uuid4(),
                article_id=uuid.uuid4(),
                title=f"Business Story {j}",
                summary="Market update.",
                source_name="Financial Times",
                importance_score=0.75,
                personal_relevance_score=0.60,
                topics=["Business"],
                is_read=False,
            )
        )

    top, changed, all_items, caught_up, intro = selector.select_briefing_items(
        candidates=candidates,
        last_session_at=utc_now() - timedelta(hours=24),
        max_items=5,
    )

    # Diversity check: Business stories must be represented
    topics = [it.candidate.topics[0] for it in all_items]
    assert "Business" in topics
    # TechWire should not occupy all 5 slots
    sources = [it.candidate.source_name for it in all_items]
    assert sources.count("TechWire") <= 3


# =============================================================================
# 9. User Timezone and Daypart Detection Test
# =============================================================================
@pytest.mark.asyncio
async def test_user_timezone_and_daypart_detection(db_session: AsyncSession):
    # Create Tokyo user (+9 UTC) and New York user (-5 UTC)
    tokyo_user = await create_user(db_session, "tokyo", tz="Asia/Tokyo")
    ny_user = await create_user(db_session, "ny", tz="America/New_York")

    engine = PersonalNewsBriefingEngine(db_session)

    tokyo_date = engine.get_user_today_date_str(tokyo_user)
    ny_date = engine.get_user_today_date_str(ny_user)

    assert isinstance(tokyo_date, str)
    assert len(tokyo_date) == 10
    assert isinstance(ny_date, str)
    assert len(ny_date) == 10

    daypart, greeting = engine.detect_daypart(tokyo_user)
    assert daypart in (Daypart.MORNING.value, Daypart.MIDDAY.value, Daypart.EVENING.value, Daypart.NIGHT.value)
    assert greeting in ("GOOD MORNING", "GOOD AFTERNOON", "GOOD EVENING")


# =============================================================================
# 10. Briefing Versioning & Midday Refresh Test
# =============================================================================
@pytest.mark.asyncio
async def test_briefing_versioning_and_refresh(db_session: AsyncSession):
    user = await create_user(db_session, "version_user")
    topic = await create_topic(db_session, "Tech", "tech-ver")
    await create_story_with_articles(db_session, "Morning Story v1", "TECHNOLOGY", topic)

    engine = PersonalNewsBriefingEngine(db_session)

    # Generate version 1 (Morning)
    v1_resp = await engine.generate_briefing(user_id=user.id, briefing_date="2026-10-07", force_refresh=False)
    assert v1_resp.version == 1

    # Add a new major story and trigger refresh (Midday v2)
    await create_story_with_articles(db_session, "Midday Breaking News v2", "TECHNOLOGY", topic, importance=0.95)
    v2_resp = await engine.generate_briefing(user_id=user.id, briefing_date="2026-10-07", force_refresh=True)
    assert v2_resp.version == 2

    # Query historical versions
    v1_loaded = await engine.get_briefing_by_date(user.id, "2026-10-07", version=1)
    v2_loaded = await engine.get_briefing_by_date(user.id, "2026-10-07", version=2)

    assert v1_loaded is not None
    assert v1_loaded.version == 1
    assert v2_loaded is not None
    assert v2_loaded.version == 2


# =============================================================================
# 11. "Caught Up" (No News) Scenario Test
# =============================================================================
@pytest.mark.asyncio
async def test_caught_up_no_news_scenario(db_session: AsyncSession):
    detector = ChangeDetector(db_session)
    selector = BriefingSelector(detector)

    # All candidates are already read and have NO new updates
    candidates = [
        EditorialCandidate(
            story_id=uuid.uuid4(),
            article_id=uuid.uuid4(),
            title="Old Story User Read",
            summary="No updates.",
            importance_score=0.50,
            personal_relevance_score=0.50,
            topics=["General"],
            is_read=True,
            user_read_percentage=1.0,
            has_meaningful_update=False,
        )
    ]

    top, changed, all_items, is_caught_up, intro = selector.select_briefing_items(
        candidates=candidates,
        last_session_at=utc_now() - timedelta(minutes=10),
    )

    assert is_caught_up is True
    assert "caught up" in intro.lower()


# =============================================================================
# 12. Failure Handling Fallback Test
# =============================================================================
@pytest.mark.asyncio
async def test_failure_handling_fallback(db_session: AsyncSession):
    user = await create_user(db_session, "fallback_user")
    topic = await create_topic(db_session, "News", "news-fb")

    # Create minimal published article
    art = Article(
        title="Emergency Fallback Headline",
        slug=f"fb-{uuid.uuid4().hex[:6]}",
        canonical_url=f"https://example.com/fb-{uuid.uuid4().hex[:6]}",
        status="PUBLISHED",
        content="Body content for emergency fallback briefing.",
    )
    art.topics = [topic]
    db_session.add(art)
    await db_session.commit()

    engine = PersonalNewsBriefingEngine(db_session)

    # Simulate error by patching candidate selector to raise exception
    engine.candidate_selector.get_candidate_pool = None  # type: ignore

    resp = await engine.generate_briefing(user_id=user.id, briefing_date="2026-10-07")
    assert resp is not None
    assert resp.status == BriefingStatus.READY.value
    assert len(resp.items) >= 1


# =============================================================================
# 13. Realistic Complex Briefing Scenario Test
# =============================================================================
@pytest.mark.asyncio
async def test_realistic_briefing_scenario(db_session: AsyncSession):
    """
    User interests: AI, Machine Learning, Technology.
    Candidates:
      A: Major AI Announcement (high relevance, high importance)
      B: Sports Event (low relevance, medium importance)
      C: Major National Event (low personal relevance, very high importance)
      D: New AI Research (high relevance, medium importance)
    Expected:
      Top 3 highlights: A, C, D
    """
    user = await create_user(db_session, "realistic_reader")
    topic_ai = await create_topic(db_session, "Artificial Intelligence", "ai-real")
    topic_sports = await create_topic(db_session, "Sports", "sports-real")
    topic_world = await create_topic(db_session, "World", "world-real")

    await add_interest(db_session, user.id, topic_ai.id, score=1.0)

    detector = ChangeDetector(db_session)
    selector = BriefingSelector(detector)

    cand_a = EditorialCandidate(
        story_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        title="Major AI Model Announcement",
        summary="A major new model was released overnight.",
        importance_score=0.88,
        personal_relevance_score=0.95,
        topics=["Artificial Intelligence"],
        primary_category="TECHNOLOGY",
        is_read=False,
    )
    cand_b = EditorialCandidate(
        story_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        title="Championship Sports Final",
        summary="Match ended in dramatic overtime victory.",
        importance_score=0.60,
        personal_relevance_score=0.15,
        topics=["Sports"],
        primary_category="SPORTS",
        is_read=False,
    )
    cand_c = EditorialCandidate(
        story_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        title="Major National Summit Accord",
        summary="Global treaty signed after marathon talks.",
        importance_score=0.98,
        personal_relevance_score=0.20,
        topics=["World"],
        primary_category="WORLD",
        is_read=False,
    )
    cand_d = EditorialCandidate(
        story_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        title="New AI Research Benchmarks",
        summary="Novel benchmark results published.",
        importance_score=0.72,
        personal_relevance_score=0.90,
        topics=["Artificial Intelligence"],
        primary_category="TECHNOLOGY",
        is_read=False,
    )

    top_items, what_changed, all_items, is_caught_up, intro = selector.select_briefing_items(
        candidates=[cand_a, cand_b, cand_c, cand_d],
        last_session_at=utc_now() - timedelta(hours=14),
        user_top_topics=["Artificial Intelligence"],
    )

    top_headlines = [it.candidate.title for it in top_items]

    # Top 3 highlights must be A, C, D (AI stories + Major National Event)
    assert any("AI Model" in h for h in top_headlines)
    assert any("National Summit" in h for h in top_headlines)
    assert any("AI Research" in h for h in top_headlines)
    assert not any("Sports" in h for h in top_headlines)


# =============================================================================
# 14. Background Briefing Generation Worker Job Test
# =============================================================================
@pytest.mark.asyncio
async def test_background_briefing_generation_job(db_session: AsyncSession):
    user = await create_user(db_session, "job_user")
    topic = await create_topic(db_session, "Technology", "tech-job")
    await add_interest(db_session, user.id, topic.id, score=1.0)
    await create_story_with_articles(db_session, "Background Worker Story", "TECHNOLOGY", topic)

    res = await briefing_generation_job()
    assert res is not None
    assert res.get("status") in ("SUCCESS", "SKIPPED", "PARTIAL")


# =============================================================================
# 15. Briefing & Session API Integration Test
# =============================================================================
@pytest.mark.asyncio
async def test_briefing_and_session_api_endpoints(db_session: AsyncSession):
    unique_email = f"briefing_api_{uuid.uuid4().hex[:6]}@example.com"
    password = "SecurePassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register user
        reg_res = await client.post(
            "/api/auth/register",
            json={"email": unique_email, "password": password, "full_name": "Briefing Reader"},
        )
        assert reg_res.status_code == 201
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Start session
        sess_start_res = await client.post("/api/news/sessions/start", headers=headers)
        assert sess_start_res.status_code == 200
        sess_id = sess_start_res.json()["session_id"]

        # 2. Send heartbeat
        hb_res = await client.post(
            f"/api/news/sessions/{sess_id}/heartbeat",
            json={"stories_viewed_delta": 2, "articles_opened_delta": 1, "has_meaningful_activity": True},
            headers=headers,
        )
        assert hb_res.status_code == 200
        assert hb_res.json()["is_active"] is True

        # 3. Fetch today's briefing
        today_res = await client.get("/api/briefings/today", headers=headers)
        assert today_res.status_code == 200
        briefing_data = today_res.json()
        assert briefing_data["title"] == "YOUR DAILY BRIEFING"
        assert briefing_data["status"] == BriefingStatus.READY.value

        # 4. Fetch status
        status_res = await client.get(f"/api/briefings/{briefing_data['briefing_date']}/status", headers=headers)
        assert status_res.status_code == 200
        assert status_res.json()["status"] == BriefingStatus.READY.value

        # 5. Fetch history
        hist_res = await client.get("/api/briefings/history", headers=headers)
        assert hist_res.status_code == 200
        assert len(hist_res.json()) >= 1

        # 6. End session
        end_res = await client.post(f"/api/news/sessions/{sess_id}/end", headers=headers)
        assert end_res.status_code == 200
        assert end_res.json()["meaningful_activity"] is True
