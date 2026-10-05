"""
test_scraper.py — Phase 5 Tests for Web Article Extraction & Scraping

Tests cover:
1. WebFetcher — robots.txt compliance, HTTP error handling
2. ContentExtractor — JSON-LD, OpenGraph, readability fallback
3. ContentCleaner — HTML stripping, truncation, reading time
4. ArticleValidator — quality gates, paywall detection
5. ScraperService — full pipeline integration with mocked HTTP calls
"""

import uuid
import sys
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# Add project root to path for scraper imports
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scraper.extractors.web_fetcher import WebFetcher, FetchResult, FetchError, RobotsError
from scraper.extractors.content_extractor import ContentExtractor, ExtractedContent
from scraper.processors.content_cleaner import ContentCleaner, CleanedContent
from scraper.processors.article_validator import ArticleValidator, ValidationResult


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name: str) -> str:
    path = os.path.join(FIXTURES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


SAMPLE_ARTICLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>AI Breakthrough in 2026 | Tech Universe</title>
  <meta property="og:title" content="AI Breakthrough in 2026" />
  <meta property="og:description" content="Researchers have achieved a new milestone in artificial intelligence." />
  <meta property="og:image" content="https://example.com/images/ai-2026.jpg" />
  <meta name="author" content="Dr. Sarah Chen" />
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": "AI Breakthrough in 2026",
    "author": {"@type": "Person", "name": "Dr. Sarah Chen"},
    "datePublished": "2026-10-05T08:00:00Z",
    "description": "Researchers have achieved a new milestone in artificial intelligence.",
    "image": "https://example.com/images/ai-2026.jpg"
  }
  </script>
</head>
<body>
  <nav>Navigation items here</nav>
  <article class="article-body">
    <h1>AI Breakthrough in 2026</h1>
    <p>Researchers at the Global AI Institute have achieved a historic milestone in
    artificial intelligence. The new model, codenamed Aurora, demonstrates unprecedented
    reasoning capabilities across multiple domains including medicine, physics, and software
    engineering.</p>
    <p>The research team, led by Dr. Sarah Chen, published their findings in Nature today.
    The model shows a 40% improvement in benchmark scores compared to previous state-of-the-art
    systems, while using 60% less compute resources.</p>
    <p>Aurora represents a fundamental shift in how neural networks process symbolic reasoning.
    Unlike previous transformer architectures, Aurora uses a hybrid approach combining
    sparse attention with explicit world model representations.</p>
    <p>Industry analysts are calling this a watershed moment for the field. "This changes
    everything we thought we knew about scaling laws," said Prof. James Liu of MIT.</p>
    <p>The model will be made available to researchers through a controlled API starting
    next month, with broader public access planned for early 2027.</p>
  </article>
  <footer>Footer content here</footer>
</body>
</html>"""


MINIMAL_HTML = """<html><head><title>Test</title></head><body><p>Short content.</p></body></html>"""


PAYWALL_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta property="og:title" content="Premium Article" />
  <meta property="og:description" content="Subscribers only. Sign in to read the full article. Create a free account to become a member." />
</head>
<body>
  <article class="article-content">
    <h1>Premium Article Title</h1>
    <p>Subscribe to read this article. Subscribers only content requires a paid account.</p>
    <p>Please sign in to read the full article. Create a free account to get started.</p>
  </article>
</body>
</html>"""


ROBOTS_TXT_DISALLOW = """User-agent: *
Disallow: /articles/
"""

ROBOTS_TXT_ALLOW = """User-agent: *
Allow: /
"""


# ---------------------------------------------------------------------------
# 1. ContentExtractor tests
# ---------------------------------------------------------------------------

class TestContentExtractor:
    def test_extracts_json_ld_metadata(self):
        """JSON-LD provides title, author, description, image, date."""
        extractor = ContentExtractor()
        result = extractor.extract(SAMPLE_ARTICLE_HTML, "https://example.com/ai-2026")

        assert result.success is True
        assert result.title == "AI Breakthrough in 2026"
        assert result.author == "Dr. Sarah Chen"
        assert result.description is not None
        assert "milestone" in result.description.lower()
        assert result.image_url == "https://example.com/images/ai-2026.jpg"
        assert result.published_at_raw == "2026-10-05T08:00:00Z"
        assert "json_ld" in result.extraction_method

    def test_extracts_body_text(self):
        """Readability heuristic extracts article body."""
        extractor = ContentExtractor()
        result = extractor.extract(SAMPLE_ARTICLE_HTML, "https://example.com/ai-2026")

        assert result.body_text is not None
        assert "Aurora" in result.body_text
        assert "Dr. Sarah Chen" in result.body_text
        assert result.word_count > 80

    def test_opengraph_fallback(self):
        """When JSON-LD is missing, OG tags are used for metadata."""
        html = """<html><head>
        <meta property="og:title" content="OG Article Title" />
        <meta property="og:description" content="This is the OG description." />
        <meta property="og:image" content="https://example.com/og.jpg" />
        </head><body>
        <article class="story-body">
          <p>This is a long article body about something interesting and important.
          It covers many aspects of the topic in great detail across multiple paragraphs.
          Readers will find this content highly informative and educational.</p>
          <p>More content follows here with additional details and analysis.
          The article continues with more paragraphs of substantive text.</p>
        </article>
        </body></html>"""

        extractor = ContentExtractor()
        result = extractor.extract(html, "https://example.com/og-test")

        assert result.title == "OG Article Title"
        assert result.image_url == "https://example.com/og.jpg"
        assert "opengraph" in result.extraction_method

    def test_returns_failure_on_empty_html(self):
        """Empty HTML returns success=False."""
        extractor = ContentExtractor()
        result = extractor.extract("", "https://example.com/empty")
        assert result.success is False

    def test_returns_failure_gracefully(self):
        """ContentExtractor never raises, even on malformed HTML."""
        extractor = ContentExtractor()
        result = extractor.extract("<not valid html <><><<<", "https://example.com/bad")
        # May or may not succeed, but must not raise
        assert isinstance(result.success, bool)

    def test_language_detected_from_html_tag(self):
        """Language detected from <html lang='...'>"""
        html = """<html lang="de"><head><title>Test</title></head>
        <body><article class="article-body">
        <p>Das ist ein langer Artikel über Wissenschaft und Technologie in Deutschland.</p>
        <p>Weitere Informationen werden hier bereitgestellt.</p>
        </article></body></html>"""
        extractor = ContentExtractor()
        result = extractor.extract(html, "https://example.de/test")
        assert result.language == "de"


# ---------------------------------------------------------------------------
# 2. ContentCleaner tests
# ---------------------------------------------------------------------------

class TestContentCleaner:
    def _make_extracted(self, **kwargs) -> ExtractedContent:
        defaults = {
            "success": True,
            "title": "Test Title",
            "author": "Test Author",
            "description": "Test description",
            "body_text": "Test body " * 50,
            "image_url": "https://example.com/img.jpg",
            "published_at_raw": None,
            "language": "en",
            "word_count": 100,
            "extraction_method": "json_ld",
        }
        defaults.update(kwargs)
        return ExtractedContent(**defaults)

    def test_strips_html_from_fields(self):
        """HTML tags are removed from text fields."""
        extracted = self._make_extracted(
            title="<b>Bold Title</b>",
            description="<p>Paragraph with <a href='#'>link</a></p>",
        )
        cleaner = ContentCleaner()
        cleaned = cleaner.clean(extracted)
        assert "<" not in (cleaned.title or "")
        assert "<" not in (cleaned.description or "")

    def test_truncates_long_description(self):
        """Descriptions longer than MAX_DESCRIPTION_CHARS are truncated."""
        long_desc = "word " * 500  # 2500 chars
        extracted = self._make_extracted(description=long_desc)
        cleaner = ContentCleaner()
        cleaned = cleaner.clean(extracted)
        assert len(cleaned.description) <= 1005  # allow small ellipsis overhead

    def test_rejects_invalid_image_url(self):
        """Non-HTTP(S) image URLs are rejected."""
        extracted = self._make_extracted(image_url="data:image/png;base64,abc123")
        cleaner = ContentCleaner()
        cleaned = cleaner.clean(extracted)
        assert cleaned.image_url is None

    def test_reading_time_estimation(self):
        """Reading time is at least 1 minute and scales with word count."""
        # ~400 words → ~2 minutes at 200 wpm
        body = "word " * 400
        extracted = self._make_extracted(body_text=body)
        cleaner = ContentCleaner()
        cleaned = cleaner.clean(extracted)
        assert cleaned.reading_time_minutes == 2

    def test_handles_none_fields(self):
        """Clean handles all-None extracted content gracefully."""
        extracted = self._make_extracted(
            title=None,
            author=None,
            description=None,
            body_text=None,
            image_url=None,
        )
        cleaner = ContentCleaner()
        cleaned = cleaner.clean(extracted)
        assert cleaned.title is None
        assert cleaned.author is None
        assert cleaned.body_text is None


# ---------------------------------------------------------------------------
# 3. ArticleValidator tests
# ---------------------------------------------------------------------------

class TestArticleValidator:
    def _make_cleaned(self, **kwargs) -> CleanedContent:
        # 8 words × 10 repetitions = 80 words
        defaults = {
            "title": "A Good Article Title",
            "author": "Test Author",
            "description": "A good description with enough words to pass validation.",
            "body_text": "This is a long article body with text. " * 10,  # 80 words
            "image_url": "https://example.com/img.jpg",
            "published_at_raw": None,
            "language": "en",
            "word_count": 80,
            "reading_time_minutes": 1,
            "extraction_method": "json_ld",
        }
        defaults.update(kwargs)
        return CleanedContent(**defaults)

    def test_valid_article_passes(self):
        """A well-formed article passes validation."""
        # 5 words × 20 = 100 words > min_word_count=50
        cleaned = self._make_cleaned(
            body_text="This is good content here. " * 20
        )
        validator = ArticleValidator(min_word_count=50)
        result = validator.validate(cleaned)
        assert result.valid is True
        assert result.has_title is True
        assert result.has_body is True

    def test_missing_title_fails(self):
        """Article without title fails validation."""
        cleaned = self._make_cleaned(title=None)
        validator = ArticleValidator(min_word_count=50)
        result = validator.validate(cleaned)
        assert result.valid is False
        assert "missing_or_short_title" in result.reasons

    def test_short_body_fails(self):
        """Article body below minimum word count fails — with no description fallback."""
        cleaned = self._make_cleaned(
            body_text="Only a few words here.",
            description=None,  # Remove description so body is the only path
        )
        validator = ArticleValidator(min_word_count=100)
        result = validator.validate(cleaned)
        assert result.valid is False

    def test_paywall_detected(self):
        """Paywall content is detected and flagged."""
        cleaned = self._make_cleaned(
            body_text="Subscribers only. Sign in to read. Create a free account to continue."
        )
        validator = ArticleValidator(min_word_count=10)
        result = validator.validate(cleaned)
        assert result.is_paywall_detected is True
        assert not result.valid

    def test_boilerplate_detected(self):
        """JavaScript-required pages are detected as boilerplate."""
        cleaned = self._make_cleaned(
            body_text="Please enable JavaScript to view this page content. JavaScript required."
        )
        validator = ArticleValidator(min_word_count=5)
        result = validator.validate(cleaned)
        assert result.valid is False

    def test_title_only_with_description_passes(self):
        """Title + description (no body) can still pass validation."""
        cleaned = self._make_cleaned(
            body_text=None,
            description="A very detailed description that covers the key points of the article clearly.",
            word_count=0,
        )
        validator = ArticleValidator(min_word_count=100)
        result = validator.validate(cleaned)
        # has_title + has_description → can pass even without body
        assert result.has_title is True
        assert result.has_description is True
        assert result.valid is True


# ---------------------------------------------------------------------------
# 4. WebFetcher tests (unit — mocked HTTP)
# ---------------------------------------------------------------------------

class TestWebFetcher:
    @pytest.mark.asyncio
    async def test_robots_txt_blocks_url(self):
        """RobotsError raised when robots.txt disallows the URL."""
        import urllib.robotparser
        fetcher = WebFetcher(respect_robots=True)

        rp = urllib.robotparser.RobotFileParser()
        rp.set_url("https://blocked.example.com/robots.txt")
        rp.parse(ROBOTS_TXT_DISALLOW.splitlines())

        # Inject the parsed robots into cache
        fetcher._robots_cache["https://blocked.example.com"] = rp

        with pytest.raises(RobotsError):
            await fetcher.fetch("https://blocked.example.com/articles/something")

    @pytest.mark.asyncio
    async def test_robots_txt_allows_url(self):
        """fetch() proceeds when robots.txt allows the URL (mocked HTTP)."""
        import urllib.robotparser
        fetcher = WebFetcher(respect_robots=True)

        rp = urllib.robotparser.RobotFileParser()
        rp.set_url("https://allowed.example.com/robots.txt")
        rp.parse(ROBOTS_TXT_ALLOW.splitlines())
        fetcher._robots_cache["https://allowed.example.com"] = rp

        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.content = SAMPLE_ARTICLE_HTML.encode("utf-8")
        mock_response.text = SAMPLE_ARTICLE_HTML
        mock_response.url = "https://allowed.example.com/article"
        mock_response.encoding = "utf-8"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = await fetcher.fetch("https://allowed.example.com/article")

        assert isinstance(result, FetchResult)
        assert result.status_code == 200
        assert "AI Breakthrough" in result.html

    @pytest.mark.asyncio
    async def test_http_error_raises_fetch_error(self):
        """HTTP 4xx/5xx raises FetchError."""
        import urllib.robotparser
        fetcher = WebFetcher(respect_robots=False)

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = b"Forbidden"
        mock_response.text = "Forbidden"
        mock_response.url = "https://example.com/article"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            with pytest.raises(FetchError) as exc_info:
                await fetcher.fetch("https://example.com/article")

        assert "403" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_robots_bypass_when_disabled(self):
        """When respect_robots=False, robots.txt is not checked."""
        fetcher = WebFetcher(respect_robots=False)

        # Even if the "cached" robots would block it
        import urllib.robotparser
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(ROBOTS_TXT_DISALLOW.splitlines())
        fetcher._robots_cache["https://blocked.example.com"] = rp

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.content = SAMPLE_ARTICLE_HTML.encode()
        mock_response.text = SAMPLE_ARTICLE_HTML
        mock_response.url = "https://blocked.example.com/articles/test"
        mock_response.encoding = "utf-8"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = await fetcher.fetch("https://blocked.example.com/articles/test")

        assert result.status_code == 200


# ---------------------------------------------------------------------------
# 5. ScraperService integration tests (mocked DB + HTTP)
# ---------------------------------------------------------------------------

class TestScraperService:
    def _make_article(
        self,
        title: str = "Test Article",
        canonical_url: str = "https://example.com/article",
        is_full_text: bool = False,
        scrape_status=None,
    ):
        article = MagicMock()
        article.id = uuid.uuid4()
        article.title = title
        article.canonical_url = canonical_url
        article.source_url = canonical_url
        article.is_full_text_available = is_full_text
        article.scrape_status = scrape_status
        article.author = None
        article.description = None
        article.image_url = None
        article.language = "en"
        article.reading_time_minutes = 2
        article.updated_at = datetime.now(timezone.utc)
        return article

    def _make_mock_session(self, article_return_value):
        """Creates a properly mocked async session returning the given article."""
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()  # NOT AsyncMock — scalar_one_or_none is sync
        mock_execute_result.scalar_one_or_none.return_value = article_return_value
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        return mock_session

    @pytest.mark.asyncio
    async def test_scrape_article_success(self):
        """Full pipeline returns SUCCESS when content is valid."""
        from app.ingestion.scraper.scraper_service import ScraperService, SCRAPE_STATUS_SUCCESS

        article = self._make_article()
        article_id = article.id
        mock_session = self._make_mock_session(article)

        mock_fetcher = AsyncMock(spec=WebFetcher)
        mock_fetcher.fetch.return_value = FetchResult(
            url=article.canonical_url,
            final_url=article.canonical_url,
            html=SAMPLE_ARTICLE_HTML,
            status_code=200,
            content_type="text/html",
        )

        service = ScraperService(session=mock_session, fetcher=mock_fetcher)
        result = await service.scrape_article(article_id)

        assert result["success"] is True
        assert result["scrape_status"] == SCRAPE_STATUS_SUCCESS
        assert result["word_count"] > 0
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_scrape_article_robots_blocked(self):
        """RobotsError maps to ROBOTS_BLOCKED status (not a fatal error)."""
        from app.ingestion.scraper.scraper_service import ScraperService, SCRAPE_STATUS_ROBOTS_BLOCKED

        article = self._make_article()
        article_id = article.id
        mock_session = self._make_mock_session(article)

        mock_fetcher = AsyncMock(spec=WebFetcher)
        mock_fetcher.fetch.side_effect = RobotsError("robots.txt disallows this URL")

        service = ScraperService(session=mock_session, fetcher=mock_fetcher)
        result = await service.scrape_article(article_id)

        assert result["success"] is False
        assert result["scrape_status"] == SCRAPE_STATUS_ROBOTS_BLOCKED
        assert "robots" in result["error"].lower()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_scrape_article_fetch_error(self):
        """FetchError maps to FAILED status (not a fatal error)."""
        from app.ingestion.scraper.scraper_service import ScraperService, SCRAPE_STATUS_FAILED

        article = self._make_article()
        article_id = article.id
        mock_session = self._make_mock_session(article)

        mock_fetcher = AsyncMock(spec=WebFetcher)
        mock_fetcher.fetch.side_effect = FetchError("HTTP 404 error", status_code=404)

        service = ScraperService(session=mock_session, fetcher=mock_fetcher)
        result = await service.scrape_article(article_id)

        assert result["success"] is False
        assert result["scrape_status"] == SCRAPE_STATUS_FAILED

    @pytest.mark.asyncio
    async def test_scrape_article_not_found(self):
        """Non-existent article returns FAILED with clear error message."""
        from app.ingestion.scraper.scraper_service import ScraperService, SCRAPE_STATUS_FAILED

        mock_session = self._make_mock_session(None)  # No article found
        service = ScraperService(session=mock_session)
        result = await service.scrape_article(uuid.uuid4())

        assert result["success"] is False
        assert result["scrape_status"] == SCRAPE_STATUS_FAILED
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_scrape_article_no_url(self):
        """Article with no URL is SKIPPED."""
        from app.ingestion.scraper.scraper_service import ScraperService, SCRAPE_STATUS_SKIPPED

        article = self._make_article(canonical_url=None)
        article.canonical_url = None
        article.source_url = None
        article_id = article.id

        mock_session = self._make_mock_session(article)
        service = ScraperService(session=mock_session)
        result = await service.scrape_article(article_id)

        assert result["scrape_status"] == SCRAPE_STATUS_SKIPPED

    @pytest.mark.asyncio
    async def test_paywall_article_validation_failed(self):
        """Paywall-gated article gets VALIDATION_FAILED status."""
        from app.ingestion.scraper.scraper_service import ScraperService, SCRAPE_STATUS_VALIDATION_FAILED

        article = self._make_article()
        article_id = article.id
        mock_session = self._make_mock_session(article)

        mock_fetcher = AsyncMock(spec=WebFetcher)
        mock_fetcher.fetch.return_value = FetchResult(
            url=article.canonical_url,
            final_url=article.canonical_url,
            html=PAYWALL_HTML,
            status_code=200,
            content_type="text/html",
        )

        service = ScraperService(session=mock_session, fetcher=mock_fetcher)
        result = await service.scrape_article(article_id)

        # Paywall causes validation failure (not a crash)
        assert result["success"] is False
        assert result["scrape_status"] == SCRAPE_STATUS_VALIDATION_FAILED
        mock_session.commit.assert_called()
