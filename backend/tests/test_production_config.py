import os
import pytest
from app.core.config import Settings, settings
from app.ai.providers.factory import get_article_analyzer
from app.ai.providers.gemini_provider import GeminiArticleAnalyzer
from app.ai.providers.mock_provider import MockArticleAnalyzer


def test_database_url_neon_sslmode_conversion():
    """Verify Neon URLs with sslmode and channel_binding are converted to asyncpg-supported ssl parameters."""
    neon_url = "postgresql://neondb_owner:npg_secret123@ep-summer-base-b5adp4fe.c-7.us-east-2.aws.neon.tech/neondb?channel_binding=require&sslmode=require"
    cleaned = Settings.assemble_database_url(neon_url)

    assert cleaned.startswith("postgresql+asyncpg://")
    assert "sslmode" not in cleaned
    assert "channel_binding" not in cleaned
    assert "ssl=require" in cleaned


def test_database_url_neon_defaults_to_ssl_require():
    """Verify Neon URLs without query parameters default to ssl=require to preserve TLS."""
    neon_url = "postgresql://neondb_owner:npg_secret123@ep-summer-base-b5adp4fe.c-7.us-east-2.aws.neon.tech/neondb"
    cleaned = Settings.assemble_database_url(neon_url)

    assert cleaned.startswith("postgresql+asyncpg://")
    assert "ssl=require" in cleaned


def test_cors_origins_include_vercel():
    """Verify production Vercel frontend origin is allowed in CORS configuration."""
    assert "https://personalized-newspaper.vercel.app" in settings.CORS_ORIGINS


def test_gemini_api_key_resolution(monkeypatch):
    """Verify Gemini API key resolution supports GEMINI_API_KEY and GOOGLE_API_KEY without crashing."""
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")

    assert settings.get_ai_api_key("gemini") == "test-gemini-key"

    analyzer = get_article_analyzer()
    assert isinstance(analyzer, GeminiArticleAnalyzer)
    assert analyzer.api_key == "test-gemini-key"
    assert "gemini" in analyzer.model.lower()


def test_gemini_missing_key_fallback(monkeypatch):
    """Verify Gemini provider gracefully falls back to MockArticleAnalyzer when key is absent."""
    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)
    monkeypatch.setattr(settings, "AI_API_KEY", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)

    analyzer = get_article_analyzer()
    assert isinstance(analyzer, MockArticleAnalyzer)
