import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_article_listing_and_pagination():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/articles?page=1&limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1
        assert data["limit"] == 3
        assert len(data["items"]) <= 3
        assert data["total"] > 0
        assert data["total_pages"] >= 1

        # Check published-only: ensure no DRAFT or ARCHIVED
        for item in data["items"]:
            assert item["status"] == "PUBLISHED"
            assert item["title"].startswith("[DEMO]")

@pytest.mark.asyncio
async def test_topic_filtering():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/articles?topic=artificial-intelligence")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0
        for item in data["items"]:
            slugs = [t["slug"] for t in item["topics"]]
            assert "artificial-intelligence" in slugs

        # Topic path endpoint
        resp2 = await client.get("/api/articles/topics/cybersecurity")
        assert resp2.status_code == 200
        data2 = resp2.json()
        for item in data2["items"]:
            slugs = [t["slug"] for t in item["topics"]]
            assert "cybersecurity" in slugs

@pytest.mark.asyncio
async def test_featured_article():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/articles/featured")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PUBLISHED"
        assert "title" in data
        assert "slug" in data
        assert len(data["topics"]) > 0

@pytest.mark.asyncio
async def test_article_detail_and_related():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Get an article from list
        list_resp = await client.get("/api/articles?limit=1")
        assert list_resp.status_code == 200
        first_art = list_resp.json()["items"][0]
        art_id = first_art["id"]

        # 2. Get detail
        detail_resp = await client.get(f"/api/articles/{art_id}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["id"] == art_id
        assert detail_data["content"] is not None
        assert "related_articles" in detail_data
        assert isinstance(detail_data["related_articles"], list)
        for rel in detail_data["related_articles"]:
            assert rel["id"] != art_id
            assert rel["status"] == "PUBLISHED"

@pytest.mark.asyncio
async def test_invalid_article_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fake_uuid = str(uuid.uuid4())
        resp = await client.get(f"/api/articles/{fake_uuid}")
        assert resp.status_code == 404

        invalid_resp = await client.get("/api/articles/invalid-uuid-string")
        assert invalid_resp.status_code == 422
