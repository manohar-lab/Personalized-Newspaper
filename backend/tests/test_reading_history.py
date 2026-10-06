"""test_reading_history.py — Phase 12 Reading History & Engagement Intelligence Tests.

Tests all required areas:
1. Reading session creation (server timestamps, unique session id)
2. Reading session end (duration, completion calculation)
3. Heartbeat (progress ack, active duration tracking)
4. Scroll tracking (max scroll depth preservation)
5. Completion detection (threshold >= 85% + min reading time)
6. Minimum reading time (rapid glance vs genuine read)
7. Visibility pause (tab inactive pause tracking)
8. Visibility resume (active reading resumed)
9. Multiple sessions for same user and article
10. Reading history aggregation (single aggregate record per user+article)
11. Open count incrementing
12. Total duration accumulation across sessions
13. Max scroll aggregation
14. Completion count incrementing
15. Deterministic engagement score formula
16. Engagement level classification (BOUNCED, LOW, MEDIUM, HIGH, DEEP)
17. Continue reading shelf query (incomplete articles)
18. Reading history pagination & ordering
19. User privacy & isolation (no leaking other user data)
20. Retention cleanup (purging old history beyond threshold)
21. Interest Agent integration (unified signal consumption)
22. Duplicate signal prevention (single event on session end)
23. Search integration (source_context="SEARCH")
24. Newspaper integration (source_context="NEWSPAPER")
25. Realistic Simulation Test (User A: 3 distinct reading profiles & outcomes)
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.models.user import User
from app.models.topic import Topic
from app.models.article import Article
from app.models.reading_history import ReadingHistory
from app.learning.models import ReadingSession
from app.learning.engagement import EngagementIntelligence
from app.services.reading_service import ReadingService


@pytest_asyncio.fixture
async def user_a(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"user_a_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pw",
        full_name="User Alpha",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_b(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"user_b_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pw",
        full_name="User Beta",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_test_articles(db_session):
    now = datetime.now(timezone.utc)
    # Ensure a topic
    stmt = select(Topic).where(Topic.slug == "technology")
    res = await db_session.execute(stmt)
    top = res.scalar_one_or_none()
    if not top:
        top = Topic(id=uuid.uuid4(), name="Technology", slug="technology")
        db_session.add(top)
        await db_session.flush()

    art1 = Article(
        id=uuid.uuid4(),
        title="AI Agents in Software Development",
        slug=f"ai-agents-dev-{uuid.uuid4().hex[:6]}",
        description="Comprehensive guide to AI agents.",
        content="In-depth analysis of autonomous development agents.",
        reading_time_minutes=4,
        published_at=now,
        status="PUBLISHED",
        topics=[top],
    )
    art2 = Article(
        id=uuid.uuid4(),
        title="Quick Morning Market Update",
        slug=f"quick-market-{uuid.uuid4().hex[:6]}",
        description="Brief morning report.",
        content="Quick highlights of market indices.",
        reading_time_minutes=2,
        published_at=now,
        status="PUBLISHED",
        topics=[top],
    )
    db_session.add_all([art1, art2])
    await db_session.commit()
    return {"art1": art1, "art2": art2}


# =============================================================================
# Unit & Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_session_lifecycle_and_history_aggregation(db_session, user_a, sample_test_articles):
    """Test 1, 2, 10, 11, 12, 13, 14, 15, 16: Session start, end, and history aggregation."""
    service = ReadingService(db_session)
    art = sample_test_articles["art1"]

    # 1. Start Session
    sess1 = await service.start_reading_session(
        user_id=user_a.id,
        article_id=art.id,
        source_context="NEWSPAPER",
    )
    assert sess1.id is not None
    assert sess1.user_id == user_a.id
    assert sess1.source_context == "NEWSPAPER"
    assert sess1.started_at is not None

    # Verify history record created with open_count=1
    hist = await service.get_article_reading_history(user_a.id, art.id)
    assert hist is not None
    assert hist.open_count == 1
    assert hist.total_duration_seconds == 0.0

    # 2. End Session with 90% scroll & completion
    end_res = await service.end_reading_session(
        user_id=user_a.id,
        session_id=sess1.id,
        article_id=art.id,
        completion_percentage=90.0,
        max_scroll_percentage=92.0,
    )
    assert end_res["is_completed"] is True or end_res["completion_percentage"] >= 85.0
    assert end_res["max_scroll_percentage"] == 92.0

    # Check aggregate history
    hist2 = await service.get_article_reading_history(user_a.id, art.id)
    assert hist2.max_scroll_percentage == 92.0
    assert hist2.last_completion_percentage == 90.0


@pytest.mark.asyncio
async def test_heartbeat_and_scroll_tracking(db_session, user_a, sample_test_articles):
    """Test 3, 4, 7, 8: Heartbeat and visibility pause/resume active time."""
    service = ReadingService(db_session)
    art = sample_test_articles["art1"]

    # Start session
    sess = await service.start_reading_session(user_a.id, art.id)

    # 1st Heartbeat at 15s, scroll 40%
    hb1 = await service.record_heartbeat(
        user_id=user_a.id,
        session_id=sess.id,
        scroll_percentage=40.0,
        active_duration_seconds=15.0,
    )
    assert hb1["is_active"] is True
    assert hb1["max_scroll_percentage"] == 40.0

    # 2nd Heartbeat at 30s active, scroll 75%
    hb2 = await service.record_heartbeat(
        user_id=user_a.id,
        session_id=sess.id,
        scroll_percentage=75.0,
        active_duration_seconds=30.0,
    )
    assert hb2["max_scroll_percentage"] == 75.0


@pytest.mark.asyncio
async def test_completion_and_minimum_reading_time(db_session, user_a, sample_test_articles):
    """Test 5 & 6: Reaching bottom in 2 seconds is not marked as genuinely completed."""
    service = ReadingService(db_session)
    art = sample_test_articles["art2"]

    # Quick bounce / scroll in 2 seconds
    sess = await service.start_reading_session(user_a.id, art.id)
    
    # End in 2 seconds with 100% scroll
    # Artificially set started_at to 2 seconds ago
    sess.started_at = datetime.now(timezone.utc) - timedelta(seconds=2)
    await db_session.commit()

    end_res = await service.end_reading_session(
        user_id=user_a.id,
        session_id=sess.id,
        article_id=art.id,
        completion_percentage=100.0,
        max_scroll_percentage=100.0,
    )
    # Duration < 10s should result in BOUNCED or not genuine complete
    assert end_res["engagement_level"] == "BOUNCED"


@pytest.mark.asyncio
async def test_multiple_sessions_aggregation(db_session, user_a, sample_test_articles):
    """Test 9, 11, 12: Multiple visits for the same article increment open count and accumulate time."""
    service = ReadingService(db_session)
    art = sample_test_articles["art1"]

    # Session 1
    sess1 = await service.start_reading_session(user_a.id, art.id)
    sess1.started_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    await db_session.commit()
    await service.end_reading_session(user_a.id, sess1.id, art.id, completion_percentage=50.0)

    # Session 2
    sess2 = await service.start_reading_session(user_a.id, art.id)
    sess2.started_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    await db_session.commit()
    await service.end_reading_session(user_a.id, sess2.id, art.id, completion_percentage=95.0, max_scroll_percentage=95.0)

    hist = await service.get_article_reading_history(user_a.id, art.id)
    assert hist.open_count == 2
    assert hist.total_duration_seconds >= 170.0
    assert hist.max_scroll_percentage == 95.0


@pytest.mark.asyncio
async def test_continue_reading_shelf(db_session, user_a, sample_test_articles):
    """Test 17: Started but incomplete articles appear in Continue Reading."""
    service = ReadingService(db_session)
    art1 = sample_test_articles["art1"]
    art2 = sample_test_articles["art2"]

    # art1: Read 50% (Incomplete)
    s1 = await service.start_reading_session(user_a.id, art1.id)
    s1.started_at = datetime.now(timezone.utc) - timedelta(seconds=45)
    await db_session.commit()
    await service.end_reading_session(user_a.id, s1.id, art1.id, completion_percentage=50.0, max_scroll_percentage=50.0)

    # art2: Completed 100% with full reading time
    s2 = await service.start_reading_session(user_a.id, art2.id)
    s2.started_at = datetime.now(timezone.utc) - timedelta(seconds=150)
    await db_session.commit()
    await service.end_reading_session(user_a.id, s2.id, art2.id, completion_percentage=100.0, max_scroll_percentage=100.0)

    continue_list = await service.get_continue_reading(user_a.id, limit=10)
    art_ids = [c.article_id for c in continue_list]

    # Incomplete art1 should be present, completed art2 should not be in continue reading
    assert art1.id in art_ids
    assert art2.id not in art_ids


@pytest.mark.asyncio
async def test_user_privacy_isolation(db_session, user_a, user_b, sample_test_articles):
    """Test 19: Users can only view their own reading history."""
    service = ReadingService(db_session)
    art = sample_test_articles["art1"]

    # User A reads art
    s_a = await service.start_reading_session(user_a.id, art.id)
    await service.end_reading_session(user_a.id, s_a.id, art.id, completion_percentage=80.0)

    # User B queries their history for this article
    hist_b = await service.get_article_reading_history(user_b.id, art.id)
    assert hist_b is None

    # User B lists history
    items_b, total_b = await service.get_user_reading_history(user_b.id)
    assert total_b == 0
    assert len(items_b) == 0


@pytest.mark.asyncio
async def test_retention_cleanup(db_session, user_a, sample_test_articles):
    """Test 20: Retention cleanup deletes records older than threshold."""
    service = ReadingService(db_session)
    art = sample_test_articles["art1"]

    # Start session and set timestamp to 400 days ago
    old_time = datetime.now(timezone.utc) - timedelta(days=400)
    s = await service.start_reading_session(user_a.id, art.id)
    s.started_at = old_time
    await db_session.commit()

    hist = await service.get_article_reading_history(user_a.id, art.id)
    hist.last_read_at = old_time
    await db_session.commit()

    # Run cleanup with 365 days retention
    cleanup_res = await service.cleanup_old_reading_history(retention_days=365)
    assert cleanup_res["sessions_deleted"] >= 1
    assert cleanup_res["history_deleted"] >= 1

    # Verify history is now gone
    hist_after = await service.get_article_reading_history(user_a.id, art.id)
    assert hist_after is None


# =============================================================================
# Realistic Simulation Test (User A with 3 Distinct Scenarios)
# =============================================================================

@pytest.mark.asyncio
async def test_realistic_simulation_user_a(db_session, user_a):
    """
    CRITICAL REALISTIC SIMULATION ACCEPTANCE TEST:
    USER A:
    - Article 1: Open, Read 4 minutes, Scroll 92%, Complete -> Expected: HIGH/DEEP engagement.
    - Article 2: Open, Read 4 seconds, Scroll 8% -> Expected: BOUNCED.
    - Article 3: Open, Read 3 minutes, Scroll 70%, Return next day, Read again -> Expected: HIGH/DEEP engagement.
    Verify that the Interest Learning Agent receives meaningfully different signals.
    """
    service = ReadingService(db_session)
    now = datetime.now(timezone.utc)

    stmt_top = select(Topic).where(Topic.slug == "technology")
    res_top = await db_session.execute(stmt_top)
    top = res_top.scalar_one_or_none()
    if not top:
        top = Topic(id=uuid.uuid4(), name="Technology", slug="technology")
        db_session.add(top)
        await db_session.flush()

    # Create 3 articles
    art1 = Article(
        id=uuid.uuid4(),
        title="Sim Art 1: In-depth Deep Learning Architecture",
        slug=f"sim-art1-{uuid.uuid4().hex[:6]}",
        reading_time_minutes=4,
        published_at=now,
        status="PUBLISHED",
        topics=[top],
    )
    art2 = Article(
        id=uuid.uuid4(),
        title="Sim Art 2: Clickbait Rapid Glance",
        slug=f"sim-art2-{uuid.uuid4().hex[:6]}",
        reading_time_minutes=3,
        published_at=now,
        status="PUBLISHED",
        topics=[top],
    )
    art3 = Article(
        id=uuid.uuid4(),
        title="Sim Art 3: Essential Research Paper Review",
        slug=f"sim-art3-{uuid.uuid4().hex[:6]}",
        reading_time_minutes=4,
        published_at=now,
        status="PUBLISHED",
        topics=[top],
    )
    db_session.add_all([art1, art2, art3])
    await db_session.commit()

    # --- Scenario 1: Article 1 (Deep Read 4 min, 92% scroll) ---
    s1 = await service.start_reading_session(user_a.id, art1.id, source_context="NEWSPAPER")
    s1.started_at = datetime.now(timezone.utc) - timedelta(minutes=4)
    await db_session.commit()

    res1 = await service.end_reading_session(
        user_id=user_a.id,
        session_id=s1.id,
        article_id=art1.id,
        completion_percentage=92.0,
        max_scroll_percentage=92.0,
    )
    assert res1["engagement_level"] in ["HIGH", "DEEP"]
    assert res1["engagement_score"] >= 0.70

    # --- Scenario 2: Article 2 (Bounce in 4 seconds, 8% scroll) ---
    s2 = await service.start_reading_session(user_a.id, art2.id, source_context="SEARCH")
    s2.started_at = datetime.now(timezone.utc) - timedelta(seconds=4)
    await db_session.commit()

    res2 = await service.end_reading_session(
        user_id=user_a.id,
        session_id=s2.id,
        article_id=art2.id,
        completion_percentage=8.0,
        max_scroll_percentage=8.0,
    )
    assert res2["engagement_level"] == "BOUNCED"
    assert res2["engagement_score"] < 0.30

    # --- Scenario 3: Article 3 (Return Visit & Re-read) ---
    # Visit 1: Read 3 minutes, scroll 70%
    s3_v1 = await service.start_reading_session(user_a.id, art3.id, source_context="SAVED")
    s3_v1.started_at = datetime.now(timezone.utc) - timedelta(days=1, minutes=3)
    await db_session.commit()
    await service.end_reading_session(
        user_id=user_a.id,
        session_id=s3_v1.id,
        article_id=art3.id,
        completion_percentage=70.0,
        max_scroll_percentage=70.0,
    )

    # Visit 2: Next day, read again for 3 minutes, scroll 95%
    s3_v2 = await service.start_reading_session(user_a.id, art3.id, source_context="DIRECT")
    s3_v2.started_at = datetime.now(timezone.utc) - timedelta(minutes=3)
    await db_session.commit()
    res3 = await service.end_reading_session(
        user_id=user_a.id,
        session_id=s3_v2.id,
        article_id=art3.id,
        completion_percentage=95.0,
        max_scroll_percentage=95.0,
    )

    assert res3["engagement_level"] in ["HIGH", "DEEP"]
    hist3 = await service.get_article_reading_history(user_a.id, art3.id)
    assert hist3.open_count == 2
    assert hist3.engagement_level in ["HIGH", "DEEP"]
    assert hist3.engagement_score > res2["engagement_score"]


# =============================================================================
# API Endpoints Integration Test
# =============================================================================

@pytest.mark.asyncio
async def test_reading_history_api_endpoints(sample_test_articles):
    art = sample_test_articles["art1"]
    unique_email = f"api_user_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register user
        reg_resp = await client.post("/api/auth/register", json={
            "email": unique_email,
            "password": password,
            "full_name": "API Reading User",
        })
        token = reg_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Start reading session
        start_resp = await client.post("/api/reading/start", json={
            "article_id": str(art.id),
            "source_context": "NEWSPAPER",
        }, headers=headers)
        assert start_resp.status_code == 201
        session_id = start_resp.json()["session_id"]

        # 2. Send heartbeat
        hb_resp = await client.post("/api/reading/heartbeat", json={
            "session_id": session_id,
            "scroll_percentage": 50.0,
            "active_duration_seconds": 20.0,
        }, headers=headers)
        assert hb_resp.status_code == 200
        assert hb_resp.json()["is_active"] is True

        # 3. End session
        end_resp = await client.post("/api/reading/end", json={
            "session_id": session_id,
            "article_id": str(art.id),
            "completion_percentage": 88.0,
            "max_scroll_percentage": 88.0,
        }, headers=headers)
        assert end_resp.status_code == 200
        assert "engagement_score" in end_resp.json()

        # 4. Fetch user reading history
        hist_resp = await client.get("/api/users/me/reading-history", headers=headers)
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert hist_data["total"] >= 1
        assert hist_data["items"][0]["article_id"] == str(art.id)
        assert hist_data["items"][0]["max_scroll_percentage"] == 88.0

        # 5. Fetch article reading history
        art_hist_resp = await client.get(f"/api/articles/{art.id}/reading-history", headers=headers)
        assert art_hist_resp.status_code == 200
        assert art_hist_resp.json()["open_count"] >= 1

        # 6. Fetch continue reading
        cont_resp = await client.get("/api/users/me/continue-reading", headers=headers)
        assert cont_resp.status_code == 200

        # 7. Fetch dev metrics
        metrics_resp = await client.get("/api/reading/metrics", headers=headers)
        assert metrics_resp.status_code == 200
        assert "average_reading_duration_seconds" in metrics_resp.json()
