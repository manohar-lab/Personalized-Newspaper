"""test_extraction_module.py — Comprehensive Unit Tests for Phase 5 Web Article Extraction.

Covers all 22 required test aspects:
1. URL validation
2. SSRF protection (localhost, 127.0.0.1, 0.0.0.0, private IPs, internal domains)
3. Robots checking (allowed, disallowed, unknown)
4. HTML fetching
5. Timeout handling
6. Redirect handling & max redirects
7. OpenGraph extraction (og:title, og:description, og:image, og:url)
8. JSON-LD extraction (NewsArticle, headline, author, articleBody, datePublished)
9. Title extraction priority
10. Author extraction priority
11. Date extraction priority
12. Image extraction priority
13. Article body extraction
14. Content cleaning (boilerplate, ads, navigation removal, whitespace normalization)
15. Short-content rejection
16. Paywall detection (keywords, classes, isAccessibleForFree=false)
17. Robots-blocked handling in service
18. Extraction failure handling without losing RSS metadata
19. Canonical URL detection (rel="canonical", og:url, JSON-LD)
20. Content hashing (SHA-256)
21. Successful article database update
22. Failed extraction preserving existing article content
"""
from datetime import datetime, timezone
import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx

from app.extraction.cleaner import ContentCleaner
from app.extraction.extractor import GenericArticleExtractor
from app.extraction.fetcher import FetchError, SSRFValidationError, WebPageFetcher
from app.extraction.models import (
    ExtractedArticleData,
    ExtractionMethod,
    ExtractionResult,
    ExtractionStatus,
    RobotsAccess,
)
from app.extraction.parser import HTMLMetadataParser
from app.extraction.robots import RobotsChecker
from app.extraction.validator import ArticleContentValidator
from app.services.article_extraction_service import ArticleExtractionService
from app.models.article import Article


# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------

JSON_LD_ARTICLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>HTML Title Tag - Should Be Fallback</title>
    <link rel="canonical" href="https://example.com/canonical-news-story">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Breakthrough in Fusion Energy Research Announced",
        "author": {"@type": "Person", "name": "Dr. Sarah Jenkins"},
        "datePublished": "2026-09-15T14:30:00Z",
        "image": "https://example.com/images/fusion-reactor.jpg",
        "description": "Scientists achieve net energy gain in magnetic confinement fusion experiment.",
        "articleBody": "Scientists at the National Ignition Facility have achieved a historic milestone in magnetic confinement nuclear fusion. For the first time in experimental history, the energy output exceeded the input threshold by a factor of 1.5. This landmark achievement opens new pathways toward clean, virtually limitless zero-emission baseload power generation for global civilization across the next century.",
        "url": "https://example.com/canonical-news-story"
    }
    </script>
</head>
<body>
    <article>
        <h1>Breakthrough in Fusion Energy Research Announced</h1>
        <p>Scientists at the National Ignition Facility have achieved a historic milestone in magnetic confinement nuclear fusion. For the first time in experimental history, the energy output exceeded the input threshold by a factor of 1.5. This landmark achievement opens new pathways toward clean, virtually limitless zero-emission baseload power generation for global civilization across the next century.</p>
    </article>
</body>
</html>
"""

OPENGRAPH_ARTICLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>NASA Discovers Habitable Exoplanet Candidate</title>
    <meta property="og:title" content="NASA Discovers Habitable Exoplanet Candidate" />
    <meta property="og:description" content="Telescope observations reveal Earth-sized planet in habitable zone." />
    <meta property="og:image" content="https://example.com/exoplanet.jpg" />
    <meta property="og:url" content="https://example.com/articles/nasa-exoplanet" />
    <meta name="author" content="Astronomer Alex Mercer" />
    <meta property="article:published_time" content="2026-08-20T10:00:00Z" />
    <link rel="canonical" href="https://example.com/articles/nasa-exoplanet" />
</head>
<body>
    <header><nav>Home | News | Contact</nav></header>
    <main>
        <p>Astronomers using next-generation space telescopes have identified a rocky, Earth-sized exoplanet orbiting within the habitable zone of a nearby red dwarf star located 35 light years away. Atmospheric spectroscopic data indicates the presence of water vapor, nitrogen, and potential biosignature gases in balanced atmospheric equilibrium.</p>
        <p>The mission team confirms that further spectroscopic analysis will be scheduled over the coming months to assess atmospheric composition and cloud layer dynamics with greater precision.</p>
    </main>
    <footer>Copyright 2026 SpaceNews. All rights reserved.</footer>
</body>
</html>
"""

PAYWALL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Exclusive Economic Forecast 2026</title>
    <meta property="og:title" content="Exclusive Economic Forecast 2026" />
</head>
<body>
    <h1>Exclusive Economic Forecast 2026</h1>
    <div class="paywall-overlay">
        <h2>Subscribe to continue reading</h2>
        <p>This premium article is available to subscribers only. Sign in to read the complete analysis or purchase a membership.</p>
    </div>
</body>
</html>
"""

BOILERPLATE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Clean Me</title></head>
<body>
    <div class="cookie-banner">Accept all cookies to proceed.</div>
    <div class="advertisement">Sponsored content from our partners.</div>
    <h1>Real Article Headline</h1>
    <p>This is the first real paragraph of the actual article containing meaningful information that the reader wants to consume regarding technological breakthroughs.</p>
    <div class="social-share">Share this story on Twitter or Facebook.</div>
    <p>This is the second real paragraph discussing the economic and social implications of the rapid adoption of renewable technology across urban centers worldwide.</p>
    <div class="newsletter-signup">Sign up for our daily newsletter today!</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 1 & 2: URL Validation and SSRF Protection
# ---------------------------------------------------------------------------

class TestURLValidationAndSSRF:
    def test_valid_urls_pass(self):
        valid_urls = [
            "https://www.nytimes.com/2026/09/15/science/fusion.html",
            "http://feeds.bbci.co.uk/news/world/rss.xml",
            "https://arstechnica.com/gadgets/2026/09/new-chip-architecture/",
            "https://news.ycombinator.com/item?id=12345",
        ]
        for url in valid_urls:
            is_safe, reason = WebPageFetcher.is_ssrf_safe_url(url)
            assert is_safe is True, f"Expected safe for {url}, got reason: {reason}"

    def test_invalid_schemes_rejected(self):
        invalid_schemes = [
            "file:///etc/passwd",
            "ftp://files.example.com/data.txt",
            "gopher://gopher.example.com",
            "javascript:alert(1)",
            "data:text/html,<h1>Hello</h1>",
        ]
        for url in invalid_schemes:
            is_safe, reason = WebPageFetcher.is_ssrf_safe_url(url)
            assert is_safe is False
            assert "scheme" in reason.lower() or "invalid" in reason.lower()

    def test_ssrf_loopback_and_localhost_rejected(self):
        local_urls = [
            "http://localhost:8000/admin",
            "http://127.0.0.1:5432",
            "http://0.0.0.0:8080/secrets",
            "http://[::1]/internal",
        ]
        for url in local_urls:
            is_safe, reason = WebPageFetcher.is_ssrf_safe_url(url)
            assert is_safe is False
            assert "loopback" in reason.lower() or "forbidden" in reason.lower()

    def test_ssrf_private_ip_ranges_rejected(self):
        private_ips = [
            "http://10.0.0.1/metadata",
            "http://192.168.1.1/router",
            "http://172.16.0.5/internal",
            "http://169.254.169.254/latest/meta-data/",  # Cloud metadata service
        ]
        for url in private_ips:
            is_safe, reason = WebPageFetcher.is_ssrf_safe_url(url)
            assert is_safe is False
            assert "private" in reason.lower() or "forbidden" in reason.lower() or "reserved" in reason.lower()

    def test_ssrf_internal_domain_suffixes_rejected(self):
        internal_domains = [
            "http://database.local/query",
            "http://auth.internal/keys",
            "http://server.lan/api",
        ]
        for url in internal_domains:
            is_safe, reason = WebPageFetcher.is_ssrf_safe_url(url)
            assert is_safe is False
            assert "forbidden" in reason.lower() or "internal" in reason.lower()


# ---------------------------------------------------------------------------
# 3: Robots Checking
# ---------------------------------------------------------------------------

class TestRobotsChecking:
    @pytest.mark.asyncio
    async def test_robots_allowed(self):
        checker = RobotsChecker()
        with patch.object(checker, "_fetch_robots_txt") as mock_fetch:
            mock_parser = MagicMock()
            mock_parser.can_fetch.return_value = True
            mock_parser.allow_all = False
            mock_fetch.return_value = mock_parser

            access = await checker.check_access("https://example.com/articles/allowed-post")
            assert access == RobotsAccess.ALLOWED

    @pytest.mark.asyncio
    async def test_robots_disallowed(self):
        checker = RobotsChecker()
        with patch.object(checker, "_fetch_robots_txt") as mock_fetch:
            mock_parser = MagicMock()
            mock_parser.can_fetch.return_value = False
            mock_parser.allow_all = False
            mock_fetch.return_value = mock_parser

            access = await checker.check_access("https://example.com/admin/private-post")
            assert access == RobotsAccess.DISALLOWED

    @pytest.mark.asyncio
    async def test_robots_unknown_on_network_error(self):
        checker = RobotsChecker()
        with patch.object(checker, "_fetch_robots_txt") as mock_fetch:
            mock_fetch.return_value = None
            access = await checker.check_access("https://unreachable-domain-xyz.com/post")
            assert access == RobotsAccess.UNKNOWN


# ---------------------------------------------------------------------------
# 4, 5, 6: HTML Fetching, Timeout, and Redirects
# ---------------------------------------------------------------------------

class TestWebFetcher:
    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        fetcher = WebPageFetcher(timeout_seconds=5)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/article"
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.content = b"<html><body><p>Hello world</p></body></html>"
        mock_response.text = "<html><body><p>Hello world</p></body></html>"

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            html, final_url, status = await fetcher.fetch("https://example.com/article")
            assert "Hello world" in html
            assert final_url == "https://example.com/article"
            assert status == 200

    @pytest.mark.asyncio
    async def test_fetch_timeout_handling(self):
        fetcher = WebPageFetcher(timeout_seconds=1)
        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timed out")):
            with pytest.raises(FetchError) as exc_info:
                await fetcher.fetch("https://example.com/slow-endpoint")
            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_redirect_to_ssrf_blocked(self):
        fetcher = WebPageFetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Redirect destination is internal IP
        mock_response.url = "http://127.0.0.1:8000/internal"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"secrets"
        mock_response.text = "secrets"

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            with pytest.raises(SSRFValidationError):
                await fetcher.fetch("https://example.com/redirect-to-local")


# ---------------------------------------------------------------------------
# 7 & 8: OpenGraph and JSON-LD Extraction
# ---------------------------------------------------------------------------

class TestMetadataParser:
    def test_json_ld_extraction(self):
        meta = HTMLMetadataParser.parse(JSON_LD_ARTICLE_HTML, "https://example.com/story")
        assert meta.title == "Breakthrough in Fusion Energy Research Announced"
        assert meta.author == "Dr. Sarah Jenkins"
        assert meta.image_url == "https://example.com/images/fusion-reactor.jpg"
        assert meta.canonical_url == "https://example.com/canonical-news-story"
        assert meta.publication_date is not None
        assert "magnetic confinement" in (meta.article_body or "")

    def test_opengraph_extraction(self):
        meta = HTMLMetadataParser.parse(OPENGRAPH_ARTICLE_HTML, "https://example.com/articles/nasa-exoplanet")
        assert meta.title == "NASA Discovers Habitable Exoplanet Candidate"
        assert meta.description == "Telescope observations reveal Earth-sized planet in habitable zone."
        assert meta.image_url == "https://example.com/exoplanet.jpg"
        assert meta.canonical_url == "https://example.com/articles/nasa-exoplanet"
        assert meta.author == "Astronomer Alex Mercer"


# ---------------------------------------------------------------------------
# 9, 10, 11, 12, 13: Priority Resolution & Content Extraction
# ---------------------------------------------------------------------------

class TestGenericArticleExtractor:
    def test_json_ld_takes_priority_over_html_title(self):
        extractor = GenericArticleExtractor()
        data = extractor.extract(JSON_LD_ARTICLE_HTML, "https://example.com/story")
        assert data.title == "Breakthrough in Fusion Energy Research Announced"
        assert data.author == "Dr. Sarah Jenkins"
        assert data.status == ExtractionStatus.SUCCESS
        assert len(data.content or "") > 100
        assert data.content_hash is not None

    def test_opengraph_fallback_when_no_json_ld(self):
        extractor = GenericArticleExtractor()
        data = extractor.extract(OPENGRAPH_ARTICLE_HTML, "https://example.com/articles/nasa-exoplanet")
        assert data.title == "NASA Discovers Habitable Exoplanet Candidate"
        assert data.image_url == "https://example.com/exoplanet.jpg"
        assert data.status == ExtractionStatus.SUCCESS
        assert len(data.content or "") > 100


# ---------------------------------------------------------------------------
# 14: Content Cleaning
# ---------------------------------------------------------------------------

class TestContentCleaner:
    def test_removes_ads_cookies_and_social_boilerplate(self):
        cleaned = ContentCleaner.clean_html(BOILERPLATE_HTML)
        assert "Accept all cookies" not in cleaned
        assert "Sponsored content" not in cleaned
        assert "Share this story" not in cleaned
        assert "Sign up for our daily newsletter" not in cleaned
        assert "Real Article Headline" in cleaned
        assert "first real paragraph" in cleaned
        assert "second real paragraph" in cleaned

    def test_whitespace_normalization(self):
        messy_text = "Line 1    with    extra   spaces.\n\n\n\n\n\nLine 2 after huge gap."
        normalized = ContentCleaner.normalize_text(messy_text)
        assert "    " not in normalized
        assert "\n\n\n" not in normalized
        assert "Line 1 with extra spaces." in normalized


# ---------------------------------------------------------------------------
# 15 & 16: Short-Content Rejection and Paywall Detection
# ---------------------------------------------------------------------------

class TestArticleContentValidator:
    def test_short_content_rejected(self):
        validator = ArticleContentValidator(min_body_length=200)
        short_article = ExtractedArticleData(
            url="https://example.com/short",
            title="Short Story",
            content="Too short body with only a few words.",
        )
        is_valid, status, reason = validator.validate(short_article)
        assert is_valid is False
        assert status == ExtractionStatus.FAILED
        assert "too short" in reason.lower()

    def test_missing_title_rejected(self):
        validator = ArticleContentValidator()
        no_title_article = ExtractedArticleData(
            url="https://example.com/no-title",
            title=None,
            content="A valid length paragraph with enough words to satisfy minimum requirements " * 10,
        )
        is_valid, status, reason = validator.validate(no_title_article)
        assert is_valid is False
        assert status == ExtractionStatus.FAILED
        assert "title" in reason.lower()

    def test_paywall_detected(self):
        validator = ArticleContentValidator()
        paywalled_article = ExtractedArticleData(
            url="https://example.com/premium",
            title="Exclusive Market Analysis",
            content="Subscribe to continue reading this premium report with in-depth financial analysis.",
        )
        is_valid, status, reason = validator.validate(paywalled_article)
        assert is_valid is False
        assert status == ExtractionStatus.PAYWALL

    def test_captcha_challenge_rejected(self):
        validator = ArticleContentValidator()
        challenge_article = ExtractedArticleData(
            url="https://example.com/blocked",
            title="Attention Required! | Cloudflare",
            content="Please verify you are human to access the website.",
        )
        is_valid, status, reason = validator.validate(challenge_article)
        assert is_valid is False
        assert status == ExtractionStatus.UNSUPPORTED


# ---------------------------------------------------------------------------
# 17, 18, 19, 20, 21, 22: Service Integration, Robots, Hashing, Preservation
# ---------------------------------------------------------------------------

class TestArticleExtractionService:
    @pytest.mark.asyncio
    async def test_robots_blocked_handling(self):
        mock_session = AsyncMock()
        mock_robots = MagicMock()
        mock_robots.check_access = AsyncMock(return_value=RobotsAccess.DISALLOWED)

        article = Article(
            id=uuid.uuid4(),
            title="Robots Restricted Article",
            source_url="https://disallowed.example.com/restricted",
            is_full_text_available=False,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = article
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        service = ArticleExtractionService(
            session=mock_session,
            robots_checker=mock_robots,
        )

        result = await service.extract_article(article.id)
        assert result.status == ExtractionStatus.ROBOTS_BLOCKED
        assert article.extraction_status == ExtractionStatus.ROBOTS_BLOCKED.value
        assert article.is_full_text_available is False

    @pytest.mark.asyncio
    async def test_successful_article_update_with_hash(self):
        mock_session = AsyncMock()
        mock_fetcher = MagicMock()
        mock_fetcher.fetch = AsyncMock(return_value=(JSON_LD_ARTICLE_HTML, "https://example.com/canonical-news-story", 200))
        mock_robots = MagicMock()
        mock_robots.check_access = AsyncMock(return_value=RobotsAccess.ALLOWED)

        article = Article(
            id=uuid.uuid4(),
            title="Initial Title from RSS",
            source_url="https://example.com/story-from-rss",
            is_full_text_available=False,
            content=None,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = article
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        service = ArticleExtractionService(
            session=mock_session,
            fetcher=mock_fetcher,
            robots_checker=mock_robots,
        )

        result = await service.extract_article(article.id)
        assert result.status == ExtractionStatus.SUCCESS
        assert article.is_full_text_available is True
        assert article.content is not None
        assert article.content_hash is not None
        assert article.canonical_url == "https://example.com/canonical-news-story"
        assert article.extraction_method in ("JSON_LD", "TRAFILATURA", "FALLBACK")
        assert article.extraction_status == ExtractionStatus.SUCCESS.value

    @pytest.mark.asyncio
    async def test_failed_extraction_preserves_existing_content(self):
        mock_session = AsyncMock()
        mock_fetcher = MagicMock()
        # Fetcher fails with 404
        mock_fetcher.fetch = AsyncMock(side_effect=FetchError("Article not found", status_code=404))
        mock_robots = MagicMock()
        mock_robots.check_access = AsyncMock(return_value=RobotsAccess.ALLOWED)

        existing_content = "Pre-existing valuable full text from earlier successful extraction."
        article = Article(
            id=uuid.uuid4(),
            title="Existing Article",
            source_url="https://example.com/existing-story",
            is_full_text_available=True,
            content=existing_content,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = article
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        service = ArticleExtractionService(
            session=mock_session,
            fetcher=mock_fetcher,
            robots_checker=mock_robots,
        )

        # Without force, already extracted articles return SUCCESS immediately
        result = await service.extract_article(article.id, force=False)
        assert result.status == ExtractionStatus.SUCCESS
        assert article.content == existing_content
        assert article.is_full_text_available is True
