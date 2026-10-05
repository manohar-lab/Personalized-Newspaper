import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.session import AsyncSessionLocal
from app.models.source import NewsSource
from app.models.feed import NewsFeed
from app.models.article import Article
from app.models.topic import Topic


@pytest.mark.asyncio
async def test_sources_and_feeds_endpoints():
    """Test GET /api/news/sources and GET /api/news/feeds"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        res_sources = await ac.get("/api/news/sources")
        assert res_sources.status_code == 200
        sources_data = res_sources.json()
        assert isinstance(sources_data, list)
        assert len(sources_data) >= 1

        res_feeds = await ac.get("/api/news/feeds")
        assert res_feeds.status_code == 200
        feeds_data = res_feeds.json()
        assert isinstance(feeds_data, list)
        assert len(feeds_data) >= 1


@pytest.mark.asyncio
async def test_unauthorized_feed_management():
    """Test 20: Unauthorized feed management endpoints receive 401 Unauthorized"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # Create feed without auth
        res_create = await ac.post(
            "/api/news/feeds",
            json={
                "source_id": str(uuid.uuid4()),
                "name": "Unauthorized Feed",
                "feed_url": "https://unauth.example.com/rss",
            },
        )
        assert res_create.status_code == 401

        # Trigger single feed ingest without auth
        res_ingest_one = await ac.post(f"/api/news/feeds/{uuid.uuid4()}/ingest")
        assert res_ingest_one.status_code == 401

        # Trigger batch ingest without auth
        res_ingest_all = await ac.post("/api/news/ingest")
        assert res_ingest_all.status_code == 401


@pytest.mark.asyncio
async def test_feed_test_endpoint():
    """Test POST /api/news/feeds/{id}/test endpoint"""
    async with AsyncSessionLocal() as session:
        source = NewsSource(
            id=uuid.uuid4(),
            name="Test Source",
            slug=f"ts-{uuid.uuid4().hex[:6]}",
            website_url="https://ts.example.com",
        )
        session.add(source)
        await session.flush()

        feed = NewsFeed(
            id=uuid.uuid4(),
            source_id=source.id,
            name="HN RSS",
            feed_url="https://news.ycombinator.com/rss",
        )
        session.add(feed)
        await session.commit()

        feed_id = feed.id

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        res = await ac.post(f"/api/news/feeds/{feed_id}/test")
        assert res.status_code == 200
        data = res.json()
        assert data["feed_url"] == "https://news.ycombinator.com/rss"
        assert "is_valid" in data


@pytest.mark.asyncio
async def test_newspaper_uses_real_ingested_articles():
    """Test 19: Personalized newspaper returns real RSS-ingested articles"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # 1. Register user
        user_email = f"reader_{uuid.uuid4().hex[:6]}@example.com"
        reg_res = await ac.post(
            "/api/auth/register",
            json={"email": user_email, "password": "password123", "full_name": "RSS Reader"},
        )
        assert reg_res.status_code == 201
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Add positive interest
        await ac.post(
            "/api/users/me/interests",
            headers=headers,
            json={
                "topic_slug": "technology",
                "interest_score": 1.0,
                "preference_type": "POSITIVE",
            },
        )

        # 3. Fetch personalized newspaper
        newspaper_res = await ac.get("/api/newspaper", headers=headers)
        assert newspaper_res.status_code == 200
        data = newspaper_res.json()

        assert "edition" in data
        assert "sections" in data
        assert len(data["sections"]) >= 1

        # Check section articles
        all_articles = []
        if data.get("featured_article"):
            all_articles.append(data["featured_article"])
        for sec in data["sections"]:
            all_articles.extend(sec["articles"])

        assert len(all_articles) > 0
        for art in all_articles:
            assert "title" in art
            assert "published_at" in art
            assert "status" in art
            assert art["status"] == "PUBLISHED"
