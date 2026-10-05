import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_get_health():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "healthy"]
    assert data["service"] == "personalized-newspaper"


@pytest.mark.asyncio
async def test_get_database_health():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/health/database")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["database"] == "postgresql"
    assert "detail" in data
