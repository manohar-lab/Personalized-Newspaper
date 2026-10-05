"""test_autonomous_pipeline.py — Phase 10 Autonomous Pipeline & Scheduler Tests."""
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.config import settings
from app.models.user import User
from app.models.topic import Topic
from app.models.interest import UserInterest
from app.models.source import NewsSource
from app.models.feed import NewsFeed
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.models.pipeline_run import PipelineRun
from app.services.news_pipeline_service import NewsPipelineService
from app.workers.scheduler import (
    start_scheduler,
    stop_scheduler,
    get_scheduler,
    get_scheduler_status,
)
from app.workers.locks import DatabaseAdvisoryLock, try_acquire_job_lock


# -----------------------------------------------------------------------------
# Fixtures & Helpers
# -----------------------------------------------------------------------------
async def create_active_user(db: AsyncSession, prefix: str = "auto_user", is_active: bool = True) -> User:
    uid = uuid.uuid4().hex[:6]
    user = User(
        email=f"{prefix}_{uid}@example.com",
        password_hash="hashed_pw",
        full_name=f"Autonomous User {uid}",
        is_active=is_active,
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


# -----------------------------------------------------------------------------
# 1 & 2. Scheduler Startup & Shutdown Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scheduler_startup_and_shutdown():
    # Start scheduler
    sched = start_scheduler()
    assert sched is not None
    assert sched.running is True

    status = get_scheduler_status()
    assert status["running"] is True
    assert status["jobs_count"] >= 5
    job_ids = [j["id"] for j in status["jobs"]]
    assert "job_fetch_feeds" in job_ids
    assert "job_extract_pending" in job_ids
    assert "job_analyze_pending" in job_ids
    assert "job_generate_daily_editions" in job_ids
    assert "job_cleanup_old_data" in job_ids

    # Shutdown
    await stop_scheduler()
    assert get_scheduler() is None
    status_after = get_scheduler_status()
    assert status_after["running"] is False
    assert status_after["jobs_count"] == 0


# -----------------------------------------------------------------------------
# 3. Feed Job Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_feed_job(db_session: AsyncSession):
    service = NewsPipelineService(db_session)
    with patch.object(
        service.ingestion_service,
        "ingest_all_active_feeds",
        new_callable=AsyncMock,
        return_value={
            "total_feeds": 3,
            "total_articles_created": 5,
            "total_duplicates_found": 2,
            "failed_feeds": 0,
        },
    ):
        res = await service.run_fetch_feeds()
        assert res["status"] == "SUCCESS"
        assert res["articles_created"] == 5

        # Check recorded PipelineRun
        stmt = select(PipelineRun).where(PipelineRun.id == uuid.UUID(res["run_id"]))
        run_record = (await db_session.execute(stmt)).scalar_one()
        assert run_record.job_type == "FETCH_FEEDS"
        assert run_record.status == "SUCCESS"
        assert run_record.items_succeeded == 5


# -----------------------------------------------------------------------------
# 4. Extraction Job Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_extraction_job(db_session: AsyncSession):
    # Create an unextracted article
    art = Article(
        title="Pending Extraction Article",
        slug=f"extract-slug-{uuid.uuid4().hex[:6]}",
        canonical_url=f"https://news.example.com/{uuid.uuid4().hex[:6]}",
        status="PUBLISHED",
        extraction_status="NOT_ATTEMPTED",
        is_full_text_available=False,
    )
    db_session.add(art)
    await db_session.commit()

    service = NewsPipelineService(db_session)
    with patch.object(
        service.extraction_service,
        "extract_article",
        new_callable=AsyncMock,
        return_value={"success": True, "status": "SUCCESS", "content_length": 800},
    ):
        res = await service.run_extract_pending_articles(limit=10)
        assert res["status"] in ["SUCCESS", "PARTIAL"]
        assert res["succeeded"] >= 1


# -----------------------------------------------------------------------------
# 5. AI Analysis Job Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_analysis_job(db_session: AsyncSession):
    art = Article(
        title="Pending AI Analysis Article",
        slug=f"analysis-slug-{uuid.uuid4().hex[:6]}",
        canonical_url=f"https://news.example.com/{uuid.uuid4().hex[:6]}",
        content="Artificial Intelligence and machine learning advancements in 2026.",
        status="PUBLISHED",
        is_full_text_available=True,
    )
    db_session.add(art)
    await db_session.commit()

    service = NewsPipelineService(db_session)
    with patch.object(
        service.analysis_service,
        "analyze_article",
        new_callable=AsyncMock,
        return_value={
            "article_id": str(art.id),
            "status": "SUCCESS",
            "primary_category": "TECHNOLOGY",
            "importance_score": 0.85,
        },
    ):
        res = await service.run_analyze_pending_articles(limit=10)
        assert res["status"] in ["SUCCESS", "PARTIAL"]
        assert res["succeeded"] >= 1


# -----------------------------------------------------------------------------
# 6. Daily Edition Generation Job Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_edition_generation_job(db_session: AsyncSession):
    user = await create_active_user(db_session, "auto_reader")
    topic = await create_test_topic(db_session, "Technology", "tech-auto")
    db_session.add(UserInterest(user_id=user.id, topic_id=topic.id, interest_score=1.0, preference_type="POSITIVE", source="EXPLICIT"))
    await db_session.commit()

    service = NewsPipelineService(db_session)
    res = await service.run_generate_daily_editions(target_date="2026-10-05", user_ids=[user.id])
    assert res["status"] in ["SUCCESS", "PARTIAL"]
    assert res["succeeded"] >= 1


# -----------------------------------------------------------------------------
# 7. Job Ordering & Full Autonomous Pipeline Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_full_autonomous_pipeline(db_session: AsyncSession):
    service = NewsPipelineService(db_session)
    with patch.object(service, "run_fetch_feeds", new_callable=AsyncMock, return_value={"status": "SUCCESS", "articles_created": 3}), \
         patch.object(service, "run_extract_pending_articles", new_callable=AsyncMock, return_value={"status": "SUCCESS", "succeeded": 3}), \
         patch.object(service, "run_analyze_pending_articles", new_callable=AsyncMock, return_value={"status": "SUCCESS", "succeeded": 3}), \
         patch.object(service, "run_generate_daily_editions", new_callable=AsyncMock, return_value={"status": "SUCCESS", "succeeded": 1}):

        res = await service.run_full_autonomous_pipeline()
        assert res["status"] == "SUCCESS"
        assert res["fetch"]["status"] == "SUCCESS"
        assert res["extract"]["status"] == "SUCCESS"
        assert res["analyze"]["status"] == "SUCCESS"
        assert res["generate"]["status"] == "SUCCESS"


# -----------------------------------------------------------------------------
# 8. Partial Failure Resilience Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_partial_failure_resilience(db_session: AsyncSession):
    service = NewsPipelineService(db_session)
    # Simulate extraction failing on 1 article, succeeding on 1 article
    art1 = Article(title="Art 1", slug=f"art1-{uuid.uuid4().hex[:6]}", canonical_url=f"https://a.com/{uuid.uuid4().hex[:6]}", status="PUBLISHED", extraction_status="NOT_ATTEMPTED")
    art2 = Article(title="Art 2", slug=f"art2-{uuid.uuid4().hex[:6]}", canonical_url=f"https://b.com/{uuid.uuid4().hex[:6]}", status="PUBLISHED", extraction_status="NOT_ATTEMPTED")
    db_session.add_all([art1, art2])
    await db_session.commit()

    async def mock_extract(aid):
        if aid == art1.id:
            return {"success": True, "status": "SUCCESS"}
        raise RuntimeError("Network timeout")

    with patch.object(service.extraction_service, "extract_article", side_effect=mock_extract):
        res = await service.run_extract_pending_articles(limit=2)
        # Should record partial success rather than crashing
        assert res["status"] in ["PARTIAL", "FAILED", "SUCCESS"]
        assert res["succeeded"] >= 1
        assert res["failed"] >= 1


# -----------------------------------------------------------------------------
# 9. Concurrency Protection & Advisory Lock Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrency_protection(db_session: AsyncSession):
    service1 = NewsPipelineService(db_session)
    # When advisory lock is acquired by one runner, a concurrent attempt should be skipped
    async with try_acquire_job_lock(db_session, "test_job") as acquired:
        assert acquired is True
        # Secondary check with mock to simulate concurrent locked execution
        with patch("app.services.news_pipeline_service.try_acquire_job_lock") as mock_lock:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = False
            mock_cm.__aexit__.return_value = None
            mock_lock.return_value = mock_cm

            res = await service1.run_fetch_feeds()
            assert res["status"] == "SKIPPED"


# -----------------------------------------------------------------------------
# 10. Inactive User Filtering Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_inactive_user_filtering(db_session: AsyncSession):
    inactive_user = await create_active_user(db_session, "inactive", is_active=False)
    service = NewsPipelineService(db_session)

    # Inactive user must not be processed
    with patch.object(service.newspaper_service, "generate_daily_edition", new_callable=AsyncMock) as mock_gen:
        res = await service.run_generate_daily_editions(target_date="2026-10-05")
        # Ensure generate_daily_edition was not called for inactive_user
        called_user_ids = [call.args[0] if call.args else call.kwargs.get("user_id") for call in mock_gen.call_args_list]
        assert inactive_user.id not in called_user_ids


# -----------------------------------------------------------------------------
# 11. Cleanup Old Data Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cleanup_old_data(db_session: AsyncSession):
    # Insert old pipeline run
    old_time = datetime.now(timezone.utc) - timedelta(days=45)
    old_run = PipelineRun(
        job_type="FETCH_FEEDS",
        status="SUCCESS",
        started_at=old_time,
        created_at=old_time,
    )
    db_session.add(old_run)
    await db_session.commit()

    service = NewsPipelineService(db_session)
    res = await service.run_cleanup_old_data(retention_days=30)
    assert res["status"] == "SUCCESS"
    assert res["deleted_runs"] >= 1


# -----------------------------------------------------------------------------
# 12. Health Endpoint Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "database" in data
        assert "scheduler" in data


# -----------------------------------------------------------------------------
# 13. Admin Pipeline Status & Trigger Endpoints Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_pipeline_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register user for auth
        unique_email = f"admin_{uuid.uuid4().hex[:6]}@example.com"
        reg_res = await client.post("/api/auth/register", json={"email": unique_email, "password": "Password123!", "full_name": "Admin User"})
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Pipeline status
        status_res = await client.get("/api/admin/pipeline/status", headers=headers)
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert "scheduler" in status_data
        assert "pipeline" in status_data

        # 2. Pipeline runs list
        runs_res = await client.get("/api/admin/pipeline/runs", headers=headers)
        assert runs_res.status_code == 200
        assert isinstance(runs_res.json(), list)

        # 3. Manual triggers
        with patch.object(NewsPipelineService, "run_fetch_feeds", new_callable=AsyncMock, return_value={"status": "SUCCESS"}), \
             patch.object(NewsPipelineService, "run_extract_pending_articles", new_callable=AsyncMock, return_value={"status": "SUCCESS"}), \
             patch.object(NewsPipelineService, "run_analyze_pending_articles", new_callable=AsyncMock, return_value={"status": "SUCCESS"}), \
             patch.object(NewsPipelineService, "run_generate_daily_editions", new_callable=AsyncMock, return_value={"status": "SUCCESS"}), \
             patch.object(NewsPipelineService, "run_full_autonomous_pipeline", new_callable=AsyncMock, return_value={"status": "SUCCESS"}):

            fetch_trig = await client.post("/api/admin/pipeline/trigger/fetch", headers=headers)
            assert fetch_trig.status_code == 200

            extract_trig = await client.post("/api/admin/pipeline/trigger/extract", headers=headers)
            assert extract_trig.status_code == 200

            analyze_trig = await client.post("/api/admin/pipeline/trigger/analyze", headers=headers)
            assert analyze_trig.status_code == 200

            gen_trig = await client.post("/api/admin/pipeline/trigger/generate", headers=headers)
            assert gen_trig.status_code == 200

            all_trig = await client.post("/api/admin/pipeline/trigger/all", headers=headers)
            assert all_trig.status_code == 200


# -----------------------------------------------------------------------------
# 14. End-to-End Autonomous Pipeline Integration Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_end_to_end_autonomous_pipeline(db_session: AsyncSession):
    """
    Simulates complete cycle:
    New article discovered -> Content extracted -> AI analyzed -> User edition generated with the article.
    """
    user = await create_active_user(db_session, "e2e_reader")
    topic = await create_test_topic(db_session, "Autonomous AI", "auto-ai-topic")
    db_session.add(UserInterest(user_id=user.id, topic_id=topic.id, interest_score=1.0, preference_type="POSITIVE", source="EXPLICIT"))
    await db_session.commit()

    # 1. Discovery
    art = Article(
        title="Autonomous AI Models Deploy Enterprise Systems",
        slug=f"e2e-{uuid.uuid4().hex[:6]}",
        canonical_url=f"https://e2e-news.com/{uuid.uuid4().hex[:6]}",
        description="Autonomous AI models deploy enterprise architectures seamlessly.",
        status="PUBLISHED",
        extraction_status="NOT_ATTEMPTED",
        is_full_text_available=False,
    )
    art.topics = [topic]
    db_session.add(art)
    await db_session.commit()
    await db_session.refresh(art)

    # 2. Autonomous pipeline execution
    service = NewsPipelineService(db_session)
    # Simulate web extraction success
    art.content = "Autonomous AI models deploy enterprise architectures seamlessly with full validation."
    art.is_full_text_available = True
    art.extraction_status = "SUCCESS"
    art.extracted_at = datetime.now(timezone.utc)
    db_session.add(art)

    # Simulate AI analysis success
    ana = ArticleAnalysis(
        article_id=art.id,
        primary_category="TECHNOLOGY",
        importance_score=0.90,
        summary="Key breakthrough in autonomous enterprise AI deployment.",
        embedding=[0.2] * 384,
        analysis_status="SUCCESS",
        analyzed_at=datetime.now(timezone.utc),
    )
    db_session.add(ana)
    await db_session.commit()

    # 3. Generate daily edition
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    edition_res = await service.newspaper_service.generate_daily_edition(user.id, today_str, force_regenerate=True)

    assert edition_res is not None
    assert edition_res.total_stories >= 1
    all_story_titles = []
    if edition_res.lead_story:
        all_story_titles.append(edition_res.lead_story.title)
    for sec in edition_res.sections:
        for st in sec.stories:
            all_story_titles.append(st.title)

    assert art.title in all_story_titles
