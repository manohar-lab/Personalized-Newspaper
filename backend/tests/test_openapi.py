import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_openapi_json_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/openapi.json")

    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert "paths" in data
    assert len(data["paths"]) > 0
    # Ensure news session start endpoint schema is present and valid
    assert "/api/news/sessions/start" in data["paths"]


@pytest.mark.asyncio
async def test_docs_and_redoc_endpoints():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        docs_res = await ac.get("/api/docs")
        redoc_res = await ac.get("/api/redoc")

    assert docs_res.status_code == 200
    assert "swagger-ui" in docs_res.text.lower()

    assert redoc_res.status_code == 200
    assert "redoc" in redoc_res.text.lower()
