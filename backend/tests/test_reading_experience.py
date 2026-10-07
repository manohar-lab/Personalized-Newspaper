"""test_reading_experience.py — Phase 21 Premium Personal News Reading Experience Tests.

Comprehensive validation of:
1. Story page retrieval (/api/stories/{slug}) with timeline, coverage, what_changed, personal relevance
2. Full article reader (/api/articles/{id})
3. Reading state tracking (/api/articles/{id}/reading-state)
4. Reading session start (/api/articles/{id}/reading/start)
5. Reading progress heartbeats (/api/articles/{id}/reading/progress)
6. Reading completion (/api/articles/{id}/reading/complete)
7. Paywall state (PAYWALL without fabricated body)
8. Robots-blocked state (ROBOTS_BLOCKED)
9. Extraction failure state (FAILED)
10. Story timeline API
11. Multi-source coverage API
12. Syndication and independent source count
13. Related stories API
14. Personal relevance reason generation
15. What changed detection
16. Article actions (Like, Save, Not-Interested)
17. Behavioral learning engagement signals
18. User privacy & isolation
19. Error states (404s, invalid payloads)
20. Realistic Multi-Source Story Simulation Test
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
from app.models.source import NewsSource
from app.models.reading_history import ReadingHistory
from app.story_intelligence.models import Story, StoryArticle
from app.story_intelligence.story_service import StoryIntelligenceService
from app.services.reading_service import ReadingService
from app.core.security import create_access_token


@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"reader_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pw",
        full_name="Premium Reader",
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
        email=f"other_{uuid.uuid4().hex[:8]}@example.com",
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
async def second_auth_headers(second_user):
    token = create_access_token(subject=second_user.id)
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


@pytest_asyncio.fixture
async def sample_story_and_articles(db_session, tech_topic):
    now = datetime.now(timezone.utc)
    
    # Create sources
    src1 = NewsSource(
        id=uuid.uuid4(),
        name="TechChronicle",
        slug=f"techchronicle-{uuid.uuid4().hex[:6]}",
        website_url="https://techchronicle.example.com",
    )
    src2 = NewsSource(
        id=uuid.uuid4(),
        name="AI Insider",
        slug=f"ai-insider-{uuid.uuid4().hex[:6]}",
        website_url="https://aiinsider.example.com",
    )
    db_session.add_all([src1, src2])
    await db_session.flush()

    art1 = Article(
        id=uuid.uuid4(),
        title="AI Company Releases New Model",
        slug=f"ai-company-releases-new-model-{uuid.uuid4().hex[:6]}",
        description="A major AI company announced their newest frontier reasoning model.",
        content="Technical details reveal significant architectural leaps in reasoning and efficiency.\n\nThe new model demonstrates state of the art performance on standardized benchmarks.",
        source_name="TechChronicle",
        source_url="https://techchronicle.example.com/new-ai-model",
        source_id=src1.id,
        author="Jane Doe",
        published_at=now - timedelta(hours=2),
        created_at=now - timedelta(hours=2),
        reading_time_minutes=4,
        status="PUBLISHED",
        extraction_status="SUCCESS",
        topics=[tech_topic],
    )

    art2 = Article(
        id=uuid.uuid4(),
        title="Benchmarks and Analysis on the New Model",
        slug=f"benchmarks-analysis-new-model-{uuid.uuid4().hex[:6]}",
        description="Independent testing demonstrates 20% latency reduction.",
        content="Deep dive into memory footprint and inference costs across major cloud providers.",
        source_name="AI Insider",
        source_url="https://aiinsider.example.com/benchmarks",
        source_id=src2.id,
        author="John Smith",
        published_at=now - timedelta(minutes=30),
        created_at=now - timedelta(minutes=30),
        reading_time_minutes=3,
        status="PUBLISHED",
        extraction_status="SUCCESS",
        topics=[tech_topic],
    )

    db_session.add_all([art1, art2])
    await db_session.flush()

    story_id = uuid.uuid4()
    story = Story(
        id=story_id,
        title="AI Company Releases New Model",
        slug=f"ai-company-releases-new-model-{uuid.uuid4().hex[:6]}",
        summary="Frontier reasoning model unveiled with high benchmark efficiency and lower latency.",
        status="DEVELOPING",
        importance_score=0.92,
        quality_score=0.88,
        activity_score=0.85,
        article_count=2,
        source_count=2,
        independent_source_count=2,
        first_published_at=now - timedelta(hours=2),
        last_updated_at=now - timedelta(minutes=30),
        primary_topic_id=tech_topic.id,
        primary_article_id=art1.id,
        latest_article_id=art2.id,
    )
    db_session.add(story)
    await db_session.flush()

    sa1 = StoryArticle(
        id=uuid.uuid4(),
        story_id=story.id,
        article_id=art1.id,
        relationship_type="PRIMARY",
        similarity_score=1.0,
        added_at=now - timedelta(hours=2),
    )
    sa2 = StoryArticle(
        id=uuid.uuid4(),
        story_id=story.id,
        article_id=art2.id,
        relationship_type="UPDATE",
        similarity_score=0.85,
        added_at=now - timedelta(minutes=30),
    )
    db_session.add_all([sa1, sa2])
    await db_session.commit()

    return story, art1, art2


@pytest.mark.asyncio
async def test_story_detail_api(sample_story_and_articles, auth_headers):
    """Test GET /api/stories/{slug} returns rich story detail with personal relevance and what_changed."""
    story, art1, art2 = sample_story_and_articles

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/stories/{story.slug}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(story.id)
        assert data["title"] == story.title
        assert data["status"] == "DEVELOPING"
        assert data["article_count"] == 2
        assert data["source_count"] == 2
        assert "personal_relevance_reason" in data
        assert "Technology" in data["personal_relevance_reason"]
        assert data["what_changed"] is not None
        assert len(data["timeline"]) == 2
        assert len(data["articles"]) == 2


@pytest.mark.asyncio
async def test_story_timeline_api(sample_story_and_articles):
    """Test GET /api/stories/{id}/timeline returns chronological items."""
    story, art1, art2 = sample_story_and_articles

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/stories/{story.id}/timeline")
        assert response.status_code == 200
        timeline = response.json()
        assert len(timeline) == 2
        assert timeline[0]["title"] == art1.title


@pytest.mark.asyncio
async def test_story_coverage_api(sample_story_and_articles):
    """Test GET /api/stories/{id}/coverage returns grouped perspectives and source counts."""
    story, art1, art2 = sample_story_and_articles

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/stories/{story.id}/coverage")
        assert response.status_code == 200
        cov = response.json()
        assert cov["story_id"] == str(story.id)
        assert cov["total_sources"] == 2
        assert cov["independent_source_count"] == 2
        assert "PRIMARY" in cov["articles_by_relationship"]
        assert "UPDATE" in cov["articles_by_relationship"]


@pytest.mark.asyncio
async def test_story_related_api(sample_story_and_articles):
    """Test GET /api/stories/{id}/related returns related story list."""
    story, art1, art2 = sample_story_and_articles

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/stories/{story.id}/related?limit=3")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_article_detail_api(sample_story_and_articles, auth_headers):
    """Test GET /api/articles/{id} returns clean article content and metadata."""
    story, art1, art2 = sample_story_and_articles

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/articles/{art1.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(art1.id)
        assert data["title"] == art1.title
        assert data["content"] == art1.content
        assert data["author"] == "Jane Doe"
        assert data["source_name"] == "TechChronicle"
        assert data["source_url"] == "https://techchronicle.example.com/new-ai-model"
        assert data["reading_time_minutes"] == 4
        assert data["personal_relevance_reason"] is not None


@pytest.mark.asyncio
async def test_paywall_article_state(db_session, tech_topic, auth_headers):
    """Test paywalled article extraction status does not fabricate content."""
    now = datetime.now(timezone.utc)
    paywall_art = Article(
        id=uuid.uuid4(),
        title="Exclusive Investigation into Frontier AI",
        slug=f"exclusive-investigation-ai-{uuid.uuid4().hex[:6]}",
        description="Behind the paywall analysis.",
        content=None,
        source_name="Financial Times",
        source_url="https://ft.example.com/exclusive-ai",
        published_at=now,
        created_at=now,
        reading_time_minutes=5,
        status="PUBLISHED",
        extraction_status="PAYWALL",
        topics=[tech_topic],
    )
    db_session.add(paywall_art)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/articles/{paywall_art.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["extraction_status"] == "PAYWALL"
        assert data["content"] is None
        assert data["source_url"] == "https://ft.example.com/exclusive-ai"


@pytest.mark.asyncio
async def test_robots_blocked_article_state(db_session, tech_topic, auth_headers):
    """Test robots-blocked article returns appropriate status and source URL."""
    now = datetime.now(timezone.utc)
    robots_art = Article(
        id=uuid.uuid4(),
        title="Robots Policy Blocked News",
        slug=f"robots-blocked-news-{uuid.uuid4().hex[:6]}",
        description="Snippet from search index.",
        content=None,
        source_name="Protected News",
        source_url="https://protected.example.com/news",
        published_at=now,
        created_at=now,
        reading_time_minutes=3,
        status="PUBLISHED",
        extraction_status="ROBOTS_BLOCKED",
        topics=[tech_topic],
    )
    db_session.add(robots_art)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/articles/{robots_art.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["extraction_status"] == "ROBOTS_BLOCKED"
        assert data["content"] is None


@pytest.mark.asyncio
async def test_reading_lifecycle_and_tracking(sample_story_and_articles, auth_headers, test_user, db_session):
    """Test full reading session lifecycle: start, heartbeat/progress, reading-state, completion."""
    story, art1, art2 = sample_story_and_articles

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Check initial reading state (should have no history)
        res_init = await client.get(f"/api/articles/{art1.id}/reading-state", headers=auth_headers)
        assert res_init.status_code == 200
        assert res_init.json()["has_history"] is False

        # 2. Start reading session
        res_start = await client.post(
            f"/api/articles/{art1.id}/reading/start?source_context=NEWSPAPER",
            headers=auth_headers,
        )
        assert res_start.status_code == 201
        start_data = res_start.json()
        session_id = start_data["session_id"]
        assert start_data["article_id"] == str(art1.id)

        # 3. Report reading progress (70% scroll, 45 seconds active)
        res_prog = await client.post(
            f"/api/articles/{art1.id}/reading/progress?session_id={session_id}&scroll_percentage=70.0&active_duration_seconds=45.0",
            headers=auth_headers,
        )
        assert res_prog.status_code == 200
        prog_data = res_prog.json()
        assert prog_data["max_scroll_percentage"] == 70.0

        # 4. Check reading-state (should reflect current progress for resume reading)
        res_state = await client.get(f"/api/articles/{art1.id}/reading-state", headers=auth_headers)
        assert res_state.status_code == 200
        state_data = res_state.json()
        assert state_data["has_history"] is True
        assert state_data["last_scroll_percentage"] == 70.0

        # 5. Complete reading session (95% scroll)
        res_end = await client.post(
            f"/api/articles/{art1.id}/reading/complete?session_id={session_id}&completion_percentage=95.0&max_scroll_percentage=95.0",
            headers=auth_headers,
        )
        assert res_end.status_code == 200
        end_data = res_end.json()
        assert end_data["max_scroll_percentage"] == 95.0
        assert end_data["is_completed"] is True


@pytest.mark.asyncio
async def test_article_actions_and_feedback(sample_story_and_articles, auth_headers):
    """Test Save, Like, and Not-Interested article action endpoints."""
    story, art1, art2 = sample_story_and_articles

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Save
        res_save = await client.post(f"/api/articles/{art1.id}/save", headers=auth_headers)
        assert res_save.status_code == 200
        assert res_save.json()["action"] == "SAVE"

        # Like
        res_like = await client.post(f"/api/articles/{art1.id}/like", headers=auth_headers)
        assert res_like.status_code == 200
        assert res_like.json()["action"] == "LIKE"

        # Not Interested
        res_not_int = await client.post(f"/api/articles/{art2.id}/not-interested", headers=auth_headers)
        assert res_not_int.status_code == 200
        assert res_not_int.json()["action"] == "NOT_INTERESTED"

        # Check article details reflect actions
        res_art = await client.get(f"/api/articles/{art1.id}", headers=auth_headers)
        assert res_art.status_code == 200
        art_data = res_art.json()
        assert art_data["is_saved"] is True
        assert art_data["is_liked"] is True


@pytest.mark.asyncio
async def test_user_reading_isolation(sample_story_and_articles, auth_headers, second_auth_headers):
    """Test User A's reading progress and saved articles are completely isolated from User B."""
    story, art1, art2 = sample_story_and_articles

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User A starts and scrolls
        res_start = await client.post(f"/api/articles/{art1.id}/reading/start", headers=auth_headers)
        sess_id = res_start.json()["session_id"]
        await client.post(
            f"/api/articles/{art1.id}/reading/progress?session_id={sess_id}&scroll_percentage=80.0",
            headers=auth_headers,
        )

        # User B checks reading state for same article -> must be 0% with no history
        res_user_b = await client.get(f"/api/articles/{art1.id}/reading-state", headers=second_auth_headers)
        assert res_user_b.status_code == 200
        assert res_user_b.json()["has_history"] is False
        assert res_user_b.json()["last_scroll_percentage"] == 0.0


@pytest.mark.asyncio
async def test_error_states():
    """Test graceful handling of non-existent stories or articles."""
    fake_id = uuid.uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_story = await client.get(f"/api/stories/{fake_id}")
        assert res_story.status_code == 404

        res_art = await client.get(f"/api/articles/{fake_id}")
        assert res_art.status_code == 404


@pytest.mark.asyncio
async def test_extraction_failure_state(db_session, tech_topic, auth_headers):
    """Test extraction failure returns FAILED status and no phantom body."""
    now = datetime.now(timezone.utc)
    failed_art = Article(
        id=uuid.uuid4(),
        title="Extraction Failed News Article",
        slug=f"extraction-failed-news-{uuid.uuid4().hex[:6]}",
        description="Available metadata only.",
        content=None,
        source_name="Raw Source",
        source_url="https://rawsource.example.com/failed",
        published_at=now,
        created_at=now,
        reading_time_minutes=2,
        status="PUBLISHED",
        extraction_status="FAILED",
        topics=[tech_topic],
    )
    db_session.add(failed_art)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/articles/{failed_art.id}", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["extraction_status"] == "FAILED"
        assert data["content"] is None
        assert data["source_url"] == "https://rawsource.example.com/failed"


@pytest.mark.asyncio
async def test_unlike_and_unsave_actions(sample_story_and_articles, auth_headers):
    """Test removing like and unsaving an article."""
    story, art1, art2 = sample_story_and_articles

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Save then unsave
        await client.post(f"/api/articles/{art1.id}/save", headers=auth_headers)
        res_unsave = await client.delete(f"/api/articles/{art1.id}/save", headers=auth_headers)
        assert res_unsave.status_code == 200
        assert res_unsave.json()["success"] is True

        # Like then unlike
        await client.post(f"/api/articles/{art1.id}/like", headers=auth_headers)
        res_unlike = await client.delete(f"/api/articles/{art1.id}/like", headers=auth_headers)
        assert res_unlike.status_code == 200
        assert res_unlike.json()["success"] is True



@pytest.mark.asyncio
async def test_realistic_multi_source_story_test(db_session, tech_topic, auth_headers):
    """
    Realistic Story Test:
    Story: 'AI Company Releases New Model'
    Coverage: 6 articles across multiple perspectives.
    Expected: Story page with headline, summary, 6-source coverage, timeline, what_changed, full primary article.
    """
    now = datetime.now(timezone.utc)
    
    articles = []
    sources = ["TechCrunch", "The Verge", "Ars Technica", "VentureBeat", "Reuters", "Wired"]
    for i, src_name in enumerate(sources):
        src = NewsSource(
            id=uuid.uuid4(),
            name=src_name,
            slug=f"{src_name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:4]}",
            website_url=f"https://{src_name.lower().replace(' ', '')}.example.com",
        )
        db_session.add(src)
        await db_session.flush()

        art = Article(
            id=uuid.uuid4(),
            title=f"Perspective {i+1}: AI Frontier Model Breakthrough by {src_name}",
            slug=f"ai-breakthrough-perspective-{i+1}-{uuid.uuid4().hex[:6]}",
            description=f"Detailed analysis from {src_name} on the new architecture.",
            content=f"Paragraph 1 covering the announcement.\n\nParagraph 2 analyzing the reasoning benchmarks and performance.\n\nParagraph 3 discussing industry impact from {src_name}.",
            source_name=src_name,
            source_url=f"https://{src_name.lower().replace(' ', '')}.example.com/ai-model-{i+1}",
            source_id=src.id,
            author=f"Author {src_name}",
            published_at=now - timedelta(minutes=(6 - i) * 20),
            created_at=now - timedelta(minutes=(6 - i) * 20),
            reading_time_minutes=4,
            status="PUBLISHED",
            extraction_status="SUCCESS",
            topics=[tech_topic],
        )
        db_session.add(art)
        articles.append(art)

    await db_session.flush()

    # Create overarching story
    story = Story(
        id=uuid.uuid4(),
        title="AI Company Releases New Frontier Model",
        slug=f"ai-company-releases-frontier-model-{uuid.uuid4().hex[:6]}",
        summary="Major technological release featuring advanced reasoning and optimized inference.",
        status="DEVELOPING",
        importance_score=0.98,
        quality_score=0.95,
        activity_score=0.92,
        article_count=6,
        source_count=6,
        independent_source_count=6,
        first_published_at=articles[0].published_at,
        last_updated_at=articles[-1].published_at,
        primary_topic_id=tech_topic.id,
        primary_article_id=articles[0].id,
        latest_article_id=articles[-1].id,
    )
    db_session.add(story)
    await db_session.flush()

    for idx, art in enumerate(articles):
        rel = "PRIMARY" if idx == 0 else ("UPDATE" if idx == 5 else "BACKGROUND")
        sa = StoryArticle(
            id=uuid.uuid4(),
            story_id=story.id,
            article_id=art.id,
            relationship_type=rel,
            similarity_score=0.9 - (idx * 0.05),
            added_at=art.published_at,
        )
        db_session.add(sa)

    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/stories/{story.slug}", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()

        assert data["title"] == "AI Company Releases New Frontier Model"
        assert data["source_count"] == 6
        assert data["article_count"] == 6
        assert len(data["timeline"]) == 6
        assert len(data["articles"]) == 6
        assert data["what_changed"] is not None
        assert "Technology" in data["personal_relevance_reason"]

