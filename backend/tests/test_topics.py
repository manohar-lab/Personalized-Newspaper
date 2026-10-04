import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_get_topics():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/topics")
        assert resp.status_code == 200
        topics = resp.json()
        assert isinstance(topics, list)
        assert len(topics) >= 17

        slugs = [t["slug"] for t in topics]
        assert "artificial-intelligence" in slugs
        assert "machine-learning" in slugs
        assert "sports" in slugs
