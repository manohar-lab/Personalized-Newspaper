import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import Settings, settings


@pytest.mark.asyncio
async def test_production_cors_get_health():
    """Verify production Vercel frontend origin receives Access-Control-Allow-Origin header on GET."""
    origin = "https://personalized-newspaper.vercel.app"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_production_cors_preflight_options_health():
    """Verify production Vercel frontend origin receives valid preflight OPTIONS response."""
    origin = "https://personalized-newspaper.vercel.app"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.options(
            "/api/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type,authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-headers" in response.headers


@pytest.mark.asyncio
async def test_production_cors_preflight_options_auth_login():
    """Verify preflight OPTIONS requests to API POST endpoints like /api/auth/login succeed."""
    origin = "https://personalized-newspaper.vercel.app"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.options(
            "/api/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_local_dev_origins_preserved():
    """Verify local development origins (localhost:3000, 127.0.0.1:3000) are preserved."""
    for origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/health", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_disallowed_origin_rejected():
    """Verify unallowed origins do not receive an Access-Control-Allow-Origin header."""
    unauthorized = "https://malicious-site.example.com"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/health", headers={"Origin": unauthorized})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_no_wildcard_cors_origin():
    """Verify wildcard '*' is not used in CORS_ORIGINS."""
    assert "*" not in settings.CORS_ORIGINS
    for origin in settings.CORS_ORIGINS:
        assert origin != "*"


def test_cors_origin_trailing_slash_normalization():
    """Verify assemble_cors_origins strips trailing slashes from comma-separated and list origins."""
    origins_str = "https://personalized-newspaper.vercel.app/,http://localhost:3000/"
    assembled = Settings.assemble_cors_origins(origins_str)
    assert "https://personalized-newspaper.vercel.app" in assembled
    assert "https://personalized-newspaper.vercel.app/" not in assembled
    assert "http://localhost:3000" in assembled
    assert "http://localhost:3000/" not in assembled

    origins_json = '["https://custom-deploy.vercel.app/"]'
    assembled_json = Settings.assemble_cors_origins(origins_json)
    assert "https://custom-deploy.vercel.app" in assembled_json
    assert "https://custom-deploy.vercel.app/" not in assembled_json


def test_frontend_url_trailing_slash_normalization():
    """Verify normalize_frontend_url strips trailing slashes."""
    url = "https://personalized-newspaper.vercel.app/"
    normalized = Settings.normalize_frontend_url(url)
    assert normalized == "https://personalized-newspaper.vercel.app"


@pytest.mark.asyncio
async def test_error_response_retains_cors_headers():
    """Verify 500 errors retain CORS headers for allowed origins."""
    origin = "https://personalized-newspaper.vercel.app"

    @app.get("/api/test-cors-error")
    async def error_route():
        raise RuntimeError("Simulated internal error")

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/test-cors-error", headers={"Origin": origin})

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"

