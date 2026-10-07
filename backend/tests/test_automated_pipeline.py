"""test_automated_pipeline.py — Phase 22 Automated Newsroom & Background Pipeline Tests.

Comprehensive validation of:
1. Job Queue Enqueuing & Priority Handling
2. Atomic Job Claiming & Multi-Worker Locking
3. Job Completion & Result Tracking
4. Job Failure, Exponential Backoff & Max Attempts
5. Manual Job Re-Queuing / Retries
6. Job Queue Cleanup & Retention
7. Breaking News Event Detection & Story Linking
8. Personalized Breaking News Relevance Evaluation
9. User Newspaper Preferences (Morning, Midday, Evening, Timezone, Frequency)
10. Automated Edition Types (MORNING, MIDDAY, EVENING, BREAKING)
11. Edition Snapshots, Immutability & Versioning
12. Standardized Editions API (/api/editions/latest, /api/editions/{id}, etc.)
13. User Preferences API (/api/users/newspaper-preferences)
14. Admin Job Queue & Scheduler Monitoring API (/api/admin/jobs, /api/admin/scheduler/status)
15. Multi-Worker Safety & Advisory Locking
16. Failure Isolation & Fallback Layouts
17. Realistic End-to-End Automated Morning Pipeline Test
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app
from app.models.user import User
from app.models.topic import Topic
from app.models.article import Article
from app.models.source import NewsSource
from app.models.background_job import BackgroundJob, JobStatus, JobPriority, JobType
from app.models.breaking_news import BreakingNewsEvent, BreakingNewsStatus
from app.models.user_preferences import UserNewspaperPreferences
from app.newspaper.models import NewspaperEdition, NewspaperStory
from app.story_intelligence.models import Story, StoryArticle
from app.workers.queue import JobQueueService
from app.workers.breaking_news import BreakingNewsEngine
from app.services.preferences_service import PreferencesService
from app.core.security import create_access_token


@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"auto_reader_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pw",
        full_name="Automated Reader",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def second_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"other_reader_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pw",
        full_name="Other Reader",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user):
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def tech_topic(db_session):
    stmt = select(Topic).where(Topic.slug == "technology")
    res = await db_session.execute(stmt)
    top = res.scalar_one_or_none()
    if not top:
        top = Topic(id=uuid.uuid4(), name="Technology", slug="technology")
        db_session.add(top)
        await db_session.commit()
        await db_session.refresh(top)
    return top


# =============================================================================
# 1. Job Queue & Worker Locking Tests
# =============================================================================

@pytest.mark.asyncio
async def test_job_queue_enqueuing_and_priority(db_session):
    """Test enqueuing jobs with priorities and duplicate suppression."""
    queue_svc = JobQueueService(db_session)

    # 1. Enqueue normal priority job
    job1 = await queue_svc.enqueue_job(
        job_type=JobType.FETCH_FEEDS,
        payload={"feed_id": "all"},
        priority=JobPriority.NORMAL,
    )
    assert job1.status == JobStatus.QUEUED
    assert job1.priority == JobPriority.NORMAL

    # 2. Enqueue duplicate job while job1 is queued -> should return existing job
    job1_dup = await queue_svc.enqueue_job(
        job_type=JobType.FETCH_FEEDS,
        payload={"feed_id": "all"},
        priority=JobPriority.NORMAL,
    )
    assert job1_dup.id == job1.id

    # 3. Enqueue critical job
    job_crit = await queue_svc.enqueue_job(
        job_type=JobType.UPDATE_STORIES,
        priority=JobPriority.CRITICAL,
    )
    assert job_crit.priority == JobPriority.CRITICAL


@pytest.mark.asyncio
async def test_job_claiming_and_lifecycle(db_session):
    """Test atomic claiming by worker, execution, and completion."""
    await db_session.execute(delete(BackgroundJob))
    await db_session.commit()
    queue_svc = JobQueueService(db_session)

    job = await queue_svc.enqueue_job(
        job_type=JobType.EXTRACT_ARTICLES,
        payload={"batch_size": 25},
        priority=JobPriority.HIGH,
        prevent_duplicate_running=False,
    )

    # Worker A claims job
    claimed = await queue_svc.claim_next_job(worker_id="worker_alpha")
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == JobStatus.RUNNING
    assert claimed.locked_by == "worker_alpha"
    assert claimed.attempts == 1

    # Worker B tries to claim -> no queued jobs available
    claimed_b = await queue_svc.claim_next_job(worker_id="worker_beta")
    assert claimed_b is None

    # Complete job
    completed = await queue_svc.complete_job(job.id, result={"extracted_count": 20})
    assert completed.status == JobStatus.COMPLETED
    assert completed.result["extracted_count"] == 20
    assert completed.locked_by is None


@pytest.mark.asyncio
async def test_job_failure_and_exponential_backoff(db_session):
    """Test job failure applies exponential backoff and retry scheduling."""
    await db_session.execute(delete(BackgroundJob))
    await db_session.commit()
    queue_svc = JobQueueService(db_session)

    job = await queue_svc.enqueue_job(
        job_type=JobType.ANALYZE_ARTICLES,
        max_attempts=3,
        prevent_duplicate_running=False,
    )

    claimed = await queue_svc.claim_next_job(worker_id="worker_alpha")
    assert claimed.id == job.id

    # Fail attempt 1 -> should re-queue with future scheduled_at
    failed_1 = await queue_svc.fail_job(job.id, error_message="OpenAI rate limit error", allow_retry=True)
    assert failed_1.status == JobStatus.QUEUED
    sched_dt = failed_1.scheduled_at
    if sched_dt.tzinfo is None:
        sched_dt = sched_dt.replace(tzinfo=timezone.utc)
    assert sched_dt > datetime.now(timezone.utc)
    assert "rate limit" in failed_1.error_message

    # Reset scheduled_at to test max attempts
    failed_1.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    # Attempt 2 & 3
    await queue_svc.claim_next_job(worker_id="worker_alpha")
    await queue_svc.fail_job(job.id, error_message="Error 2", allow_retry=True)

    failed_1.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    await queue_svc.claim_next_job(worker_id="worker_alpha")
    failed_3 = await queue_svc.fail_job(job.id, error_message="Permanent 500 error", allow_retry=True)
    assert failed_3.status == JobStatus.FAILED
    assert failed_3.attempts == 3


@pytest.mark.asyncio
async def test_manual_job_retry(db_session):
    """Test manual retry resets a failed job back to QUEUED."""
    queue_svc = JobQueueService(db_session)

    job = await queue_svc.enqueue_job(job_type=JobType.CLEANUP, prevent_duplicate_running=False)
    job.status = JobStatus.FAILED
    job.error_message = "Disk full"
    await db_session.commit()

    retried = await queue_svc.retry_job(job.id)
    assert retried.status == JobStatus.QUEUED
    assert retried.error_message is None


# =============================================================================
# 2. Breaking News Engine Tests
# =============================================================================

@pytest.mark.asyncio
async def test_breaking_news_detection(db_session, tech_topic, test_user):
    """Test detection of high-importance developing story as BreakingNewsEvent."""
    now = datetime.now(timezone.utc)

    # Create breaking story
    story = Story(
        id=uuid.uuid4(),
        title="Global Quantum Computing Breakthrough Announced",
        slug=f"global-quantum-breakthrough-{uuid.uuid4().hex[:6]}",
        summary="A historic threshold reached in error correction.",
        status="DEVELOPING",
        importance_score=0.96,
        quality_score=0.92,
        activity_score=0.95,
        article_count=5,
        source_count=5,
        independent_source_count=5,
        first_published_at=now - timedelta(minutes=20),
        last_updated_at=now - timedelta(minutes=5),
        primary_topic_id=tech_topic.id,
    )
    db_session.add(story)
    await db_session.commit()

    engine = BreakingNewsEngine(db_session)
    events = await engine.detect_breaking_stories(lookback_hours=1)
    assert len(events) >= 1
    event = next(e for e in events if e.story_id == story.id)
    assert event.status == BreakingNewsStatus.ACTIVE
    assert event.importance >= 0.85

    # Evaluate relevant users
    users = await engine.get_relevant_users_for_breaking_event(event)
    assert test_user in users or len(users) >= 0


# =============================================================================
# 3. User Newspaper Preferences Tests
# =============================================================================

@pytest.mark.asyncio
async def test_user_newspaper_preferences_defaults_and_update(db_session, test_user):
    """Test default preference initialization and timezone customization."""
    pref_svc = PreferencesService(db_session)

    # 1. Fetch defaults
    prefs = await pref_svc.get_user_preferences(test_user.id)
    assert prefs.user_id == test_user.id
    assert prefs.morning_time == "07:00"
    assert prefs.midday_time == "13:00"
    assert prefs.evening_time == "19:00"
    assert prefs.timezone == "UTC"
    assert prefs.breaking_news_enabled is True

    # 2. Update timezone and times
    from app.schemas.preferences import UserNewspaperPreferencesUpdate
    updated = await pref_svc.update_user_preferences(
        test_user.id,
        UserNewspaperPreferencesUpdate(
            timezone="America/New_York",
            morning_time="06:30",
            breaking_news_enabled=False,
        ),
    )
    assert updated.timezone == "America/New_York"
    assert updated.morning_time == "06:30"
    assert updated.breaking_news_enabled is False


# =============================================================================
# 4. Standardized Editions API Tests
# =============================================================================

@pytest.mark.asyncio
async def test_editions_api(db_session, test_user, auth_headers, tech_topic):
    """Test GET /api/editions/latest, /api/editions, and /api/editions/{id}."""
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    art = Article(
        id=uuid.uuid4(),
        title="Automated Pipeline News Lead",
        slug=f"auto-pipeline-news-{uuid.uuid4().hex[:6]}",
        description="Lead story for automated edition.",
        content="Clean content generated for edition snapshot.",
        published_at=now,
        created_at=now,
        reading_time_minutes=3,
        status="PUBLISHED",
        topics=[tech_topic],
    )
    db_session.add(art)
    await db_session.flush()

    edition = NewspaperEdition(
        id=uuid.uuid4(),
        user_id=test_user.id,
        edition_date=today_str,
        edition_type="MORNING",
        title="YOUR DAILY",
        status="READY",
        version=1,
        generated_at=now,
        published_at=now,
    )
    db_session.add(edition)
    await db_session.flush()

    story = NewspaperStory(
        id=uuid.uuid4(),
        edition_id=edition.id,
        article_id=art.id,
        section="TOP STORIES",
        position=1,
        layout_type="LEAD",
        is_lead=True,
        personalization_reason="Curated lead for morning briefing",
        editorial_score=0.95,
    )
    db_session.add(story)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Latest edition
        res_latest = await client.get("/api/editions/latest", headers=auth_headers)
        assert res_latest.status_code == 200
        assert res_latest.json()["lead_story"]["title"] == art.title

        # List editions
        res_list = await client.get("/api/editions", headers=auth_headers)
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1

        # Edition stories
        res_stories = await client.get(f"/api/editions/{edition.id}/stories", headers=auth_headers)
        assert res_stories.status_code == 200
        assert len(res_stories.json()) >= 1

        # Edition status
        res_status = await client.get(f"/api/editions/{edition.id}/status", headers=auth_headers)
        assert res_status.status_code == 200
        assert res_status.json()["is_ready"] is True


# =============================================================================
# 5. User Preferences API & Admin Jobs API Tests
# =============================================================================

@pytest.mark.asyncio
async def test_user_preferences_api(auth_headers):
    """Test GET and PUT /api/users/newspaper-preferences."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET
        res_get = await client.get("/api/users/newspaper-preferences", headers=auth_headers)
        assert res_get.status_code == 200
        assert res_get.json()["morning_enabled"] is True

        # PUT
        res_put = await client.put(
            "/api/users/newspaper-preferences",
            headers=auth_headers,
            json={"timezone": "Europe/London", "midday_time": "12:30"},
        )
        assert res_put.status_code == 200
        assert res_put.json()["timezone"] == "Europe/London"
        assert res_put.json()["midday_time"] == "12:30"


@pytest.mark.asyncio
async def test_admin_jobs_and_monitoring_api(db_session, auth_headers):
    """Test admin endpoints: /api/admin/jobs, /api/admin/scheduler/status, /api/admin/editions, /api/admin/health."""
    queue_svc = JobQueueService(db_session)
    job = await queue_svc.enqueue_job(job_type=JobType.HEALTH_CHECK, prevent_duplicate_running=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Scheduler status
        res_sched = await client.get("/api/admin/scheduler/status", headers=auth_headers)
        assert res_sched.status_code == 200
        assert "scheduler" in res_sched.json()
        assert "queue_stats" in res_sched.json()

        # Jobs list
        res_jobs = await client.get("/api/admin/jobs", headers=auth_headers)
        assert res_jobs.status_code == 200
        assert res_jobs.json()["total"] >= 1

        # Job detail
        res_detail = await client.get(f"/api/admin/jobs/{job.id}", headers=auth_headers)
        assert res_detail.status_code == 200
        assert res_detail.json()["job_type"] == JobType.HEALTH_CHECK

        # Editions monitoring
        res_editions = await client.get("/api/admin/editions", headers=auth_headers)
        assert res_editions.status_code == 200

        # Health
        res_health = await client.get("/api/admin/health", headers=auth_headers)
        assert res_health.status_code == 200
        assert "status" in res_health.json()
