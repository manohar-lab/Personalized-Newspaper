"""test_web_intelligence.py — Phase 20 Comprehensive Test Suite.

Tests all aspects of Phase 20:
- URL canonicalization & tracking parameter removal
- SSRF protection and redirect safety
- Per-domain rate limiting and 429 Retry-After handling
- Robots.txt compliance and crawl-delay
- Conditional requests (ETag / Last-Modified / 304 Not Modified)
- JSON-LD and OpenGraph metadata extraction
- Paywall, cookie consent, and JS-required page detection
- Article quality scoring
- Meaningful article versioning and content change detection
- Syndication and source independence calculation
- Source health and staleness tracking
- Fault isolation in feed ingestion
- Realistic 10-item feed test (8 valid, 1 duplicate, 1 invalid)
- Web intelligence API endpoints
"""
from datetime import datetime, timezone
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.extraction.cleaner import ContentCleaner
from app.extraction.fetcher import FetchError, FetchResponse, SSRFValidationError, WebPageFetcher
from app.extraction.models import ExtractedArticleData, ExtractionStatus, RobotsAccess
from app.extraction.quality import ArticleQualityScorer
from app.extraction.rate_limiter import DomainRateLimiter
from app.extraction.robots import RobotsChecker
from app.extraction.sources.base import BaseSourceExtractor
from app.extraction.sources.generic import GenericSourceExtractor
from app.extraction.sources.registry import ExtractorRegistry
from app.extraction.url_normalizer import URLNormalizer
from app.extraction.validator import ArticleContentValidator
from app.models.article import Article
from app.models.feed import NewsFeed
from app.models.source import NewsSource
from app.services.article_versioning_service import ArticleVersioningService
from app.services.robust_ingestion_service import RobustIngestionService
from app.services.syndication_service import SyndicationDetector


# =============================================================================
# 1. URL Normalization & Canonicalization Tests
# =============================================================================
def test_url_normalizer_strips_tracking_params():
    raw_url = "https://example.com/news/tech-breakthrough/?utm_source=twitter&utm_medium=social&utm_campaign=launch&id=9942#comments"
    normalized = URLNormalizer.normalize_url(raw_url)
    assert "utm_source" not in normalized
    assert "utm_medium" not in normalized
    assert "utm_campaign" not in normalized
    assert "#comments" not in normalized
    assert "id=9942" in normalized
    assert normalized.startswith("https://example.com/news/tech-breakthrough?id=9942")


def test_url_canonical_resolution():
    source_url = "https://www.thehindu.com/news/national/article123.ece?utm_source=feed"
    canon_url = "https://thehindu.com/news/national/article123.ece"
    resolved = URLNormalizer.resolve_canonical(source_url, canon_url)
    assert resolved == "https://thehindu.com/news/national/article123.ece"


def test_article_fingerprint_generation():
    fp1 = URLNormalizer.compute_article_fingerprint(
        "https://example.com/art1",
        "Global Economy Growth Accelerates",
        "The international monetary fund released a comprehensive report today.",
    )
    fp2 = URLNormalizer.compute_article_fingerprint(
        "https://example.com/art1?utm_source=rss",
        "global economy growth accelerates!",
        "The international monetary fund released a comprehensive report today.",
    )
    assert fp1 == fp2


# =============================================================================
# 2. SSRF Safety Tests
# =============================================================================
def test_ssrf_safety_blocks_private_and_loopback_ips():
    bad_urls = [
        "http://localhost:8000/api",
        "http://127.0.0.1/admin",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data",
        "http://internal-service.local/data",
        "ftp://example.com/file",
        "file:///etc/passwd",
    ]
    for url in bad_urls:
        is_safe, reason = WebPageFetcher.is_ssrf_safe_url(url)
        assert not is_safe, f"Expected {url} to be blocked by SSRF check, but passed"


def test_ssrf_safety_allows_legitimate_domains():
    good_urls = [
        "https://www.bbc.com/news/technology-123456",
        "https://reuters.com/business/markets-today",
        "https://thehindu.com/news/national",
        "http://example.com/rss.xml",
    ]
    for url in good_urls:
        is_safe, _ = WebPageFetcher.is_ssrf_safe_url(url)
        assert is_safe, f"Expected {url} to pass SSRF check"


# =============================================================================
# 3. Domain Rate Limiter Tests
# =============================================================================
@pytest.mark.asyncio
async def test_domain_rate_limiter_pacing():
    limiter = DomainRateLimiter(default_min_delay_seconds=0.1)
    # First access is immediate
    s1 = await limiter.acquire("https://news.example.com/article1")
    assert s1 == 0.0

    # Second immediate access is delayed to respect minimum delay
    s2 = await limiter.acquire("https://news.example.com/article2")
    assert s2 > 0.0

    # 429 backoff
    limiter.register_429_backoff("https://news.example.com/article3", retry_after_seconds=0.1)
    s3 = await limiter.acquire("https://news.example.com/article4")
    assert s3 >= 0.05


# =============================================================================
# 4. Robots.txt Compliance & Crawl Delay Tests
# =============================================================================
@pytest.mark.asyncio
async def test_robots_checker_parses_rules():
    checker = RobotsChecker()
    # Mocking parser in cache
    from urllib.robotparser import RobotFileParser
    parser = RobotFileParser()
    parser.parse([
        "User-agent: *",
        "Disallow: /private/",
        "Disallow: /admin/",
        "Crawl-delay: 2",
        "Allow: /news/",
    ])
    checker._cache["example.com"] = (parser, datetime.now().timestamp(), 2.0)

    access_allowed = await checker.check_access("https://example.com/news/article-1")
    assert access_allowed == RobotsAccess.ALLOWED

    access_blocked = await checker.check_access("https://example.com/private/secret-data")
    assert access_blocked == RobotsAccess.DISALLOWED

    crawl_delay = checker.get_crawl_delay("https://example.com/news/article-1")
    assert crawl_delay == 2.0


# =============================================================================
# 5. Conditional Requests & 304 Not Modified Tests
# =============================================================================
@pytest.mark.asyncio
async def test_fetcher_conditional_response_304(monkeypatch):
    fetcher = WebPageFetcher()

    async def mock_get(self, request_url, **kwargs):
        headers = dict(self.headers)
        if kwargs.get("headers"):
            headers.update(kwargs["headers"])
        if headers.get("If-None-Match") == '"xyz123"' or headers.get("if-none-match") == '"xyz123"':
            class Mock304Response:
                status_code = 304
                headers = {"etag": '"xyz123"'}
                url = request_url
                content = b""
                text = ""
            return Mock304Response()
        
        class Mock200Response:
            status_code = 200
            headers = {"etag": '"xyz123"', "content-type": "text/html"}
            url = request_url
            content = b"<html><body><article><p>Fresh content</p></article></body></html>"
            text = "<html><body><article><p>Fresh content</p></article></body></html>"
        return Mock200Response()

    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    # First fetch: 200 OK
    res1 = await fetcher.fetch_safe("https://example.com/feed.xml")
    assert res1.status_code == 200
    assert res1.etag == '"xyz123"'
    assert not res1.is_not_modified

    # Second fetch with ETag: 304 Not Modified
    res2 = await fetcher.fetch_safe("https://example.com/feed.xml", etag='"xyz123"')
    assert res2.status_code == 304
    assert res2.is_not_modified


# =============================================================================
# 6. JSON-LD and OpenGraph Extraction Tests
# =============================================================================
def test_json_ld_article_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ignored HTML Title</title>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": "Quantum Computing Reaches Superposition Milestone",
            "author": {"@type": "Person", "name": "Dr. Sarah Mitchell"},
            "datePublished": "2026-10-07T10:00:00Z",
            "image": "https://example.com/images/quantum.jpg",
            "description": "Physicists establish 10,000 stable physical qubits in room-temperature test.",
            "articleBody": "Physicists in Zurich have achieved a breakthrough in quantum coherence. The laboratory successfully maintained superposition for three hours under ambient atmospheric pressures. This milestone could transform semiconductor manufacturing and cryptography worldwide."
        }
        </script>
    </head>
    <body>
        <p>Short body in HTML.</p>
    </body>
    </html>
    """
    extractor = GenericSourceExtractor()
    extracted = extractor.extract(html, "https://techtimes.com/quantum-2026")

    assert extracted.status == ExtractionStatus.SUCCESS
    assert extracted.title == "Quantum Computing Reaches Superposition Milestone"
    assert extracted.author == "Dr. Sarah Mitchell"
    assert "Zurich" in (extracted.content or "")
    assert extracted.publication_date is not None
    assert extracted.quality_score >= 0.70


def test_opengraph_fallback_extraction():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta property="og:title" content="Electric Aircraft Completes Transatlantic Flight" />
        <meta property="og:description" content="Commercial aviation takes a green leap forward with zero emissions." />
        <meta property="og:image" content="https://example.com/plane.jpg" />
        <meta property="article:author" content="Marcus Vance" />
        <meta property="article:published_time" content="2026-10-06T15:30:00Z" />
        <link rel="canonical" href="https://aerospace.com/electric-flight" />
    </head>
    <body>
        <article>
            <p>An experimental electric airliner completed its inaugural transatlantic crossing yesterday without burning a drop of fossil fuel.</p>
            <p>The nine-hour flight from Shannon to Halifax utilized next-generation solid-state battery cells developed by an international consortium.</p>
            <p>Aviation authorities observed zero telemetry irregularities throughout the continuous cruising altitude phase.</p>
        </article>
    </body>
    </html>
    """
    extractor = GenericSourceExtractor()
    extracted = extractor.extract(html, "https://aerospace.com/electric-flight?utm_source=twitter")

    assert extracted.status == ExtractionStatus.SUCCESS
    assert extracted.title == "Electric Aircraft Completes Transatlantic Flight"
    assert extracted.canonical_url == "https://aerospace.com/electric-flight"
    assert "transatlantic crossing" in (extracted.content or "").lower()


# =============================================================================
# 7. Paywall, Cookie & Consent Page Detection Tests
# =============================================================================
def test_paywall_detection():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Premium Financial Market Analysis</title></head>
    <body>
        <h1>Premium Financial Market Analysis</h1>
        <div class="paywall-banner">
            <p>This premium article is available to subscribers only. Subscribe to continue reading exclusive global analysis.</p>
        </div>
    </body>
    </html>
    """
    extractor = GenericSourceExtractor()
    extracted = extractor.extract(html, "https://financialtimes.mock/premium-story")
    assert extracted.status == ExtractionStatus.PAYWALL


def test_cookie_consent_page_detection():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Privacy Preference Center</title></head>
    <body>
        <h1>We value your privacy</h1>
        <p>This website uses cookies to enhance user experience. Accept all cookies or manage cookie preferences below. Consent to our use of cookies in accordance with our GDPR consent notice.</p>
    </body>
    </html>
    """
    extractor = GenericSourceExtractor()
    extracted = extractor.extract(html, "https://site.mock/consent")
    assert extracted.status == ExtractionStatus.COOKIE_CONSENT_PAGE


def test_js_required_page_detection():
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Loading Application...</title></head>
    <body>
        <noscript>Please enable JavaScript to view this page or run this app.</noscript>
    </body>
    </html>
    """
    extractor = GenericSourceExtractor()
    extracted = extractor.extract(html, "https://spa.mock/news")
    assert extracted.status in (ExtractionStatus.JS_REQUIRED, ExtractionStatus.LOW_QUALITY, ExtractionStatus.FAILED)



# =============================================================================
# 8. Article Quality Scoring Tests
# =============================================================================
def test_quality_scorer_comprehensive_scoring():
    article = ExtractedArticleData(
        url="https://example.com/story",
        title="Major Energy Breakthrough in Hydrogen Fuel Cells",
        author="Evelyn Reed",
        description="Researchers discover scalable nickel-based catalyst.",
        publication_date=datetime.now(timezone.utc),
        image_url="https://example.com/cell.jpg",
        content=(
            "Scientists at the National Renewable Energy Laboratory announced a major breakthrough.\n\n"
            "By replacing platinum with a novel nanostructured nickel alloy, production costs drop by 80%.\n\n"
            "Commercial vehicle prototypes utilizing the new catalyst will begin road tests next quarter across three continents."
        ),
    )
    breakdown = ArticleQualityScorer.evaluate(article)
    assert breakdown.is_acceptable
    assert breakdown.overall_score >= 0.75
    assert breakdown.content_length_score >= 0.5
    assert breakdown.headline_score == 1.0
    assert breakdown.author_score == 1.0


# =============================================================================
# 9. Article Content Versioning Tests
# =============================================================================
@pytest.mark.asyncio
async def test_meaningful_article_versioning(db_session: AsyncSession):
    article = Article(
        title="Developing: Rocket Launch Delayed",
        slug="rocket-launch-delayed",
        content="The aerospace agency announced that today's launch has been postponed due to unfavorable weather.",
        content_hash="oldhash123",
        status="PUBLISHED",
        language="en",
    )
    db_session.add(article)
    await db_session.commit()

    versioning = ArticleVersioningService(db_session)

    # 1. Trivial whitespace change -> Not updated
    updated_trivial = await versioning.check_and_apply_update(
        article,
        new_content="The aerospace agency announced that today's launch has been postponed due to unfavorable weather.  ",
    )
    assert not updated_trivial

    # 2. Substantive new paragraphs added -> Updated
    new_substantive_text = (
        "The aerospace agency announced that today's launch has been postponed due to unfavorable weather.\n\n"
        "Engineers identified wind gusts exceeding 45 knots in the upper troposphere. "
        "A new 48-hour launch window has been scheduled for Friday at 06:00 UTC with favorable telemetry forecasts."
    )
    updated_substantive = await versioning.check_and_apply_update(
        article,
        new_content=new_substantive_text,
        new_title="Update: Rocket Launch Rescheduled for Friday",
    )
    assert updated_substantive
    assert article.title == "Update: Rocket Launch Rescheduled for Friday"
    assert "wind gusts exceeding 45 knots" in article.content


# =============================================================================
# 10. Syndication & Source Independence Tests
# =============================================================================
def test_syndication_detection_and_independence():
    title1 = "Central Bank Holds Benchmark Interest Rate Steady"
    title2 = "Central Bank Holds Benchmark Interest Rate Steady (AP)"
    content1 = "WASHINGTON (AP) — The Federal Reserve maintained its benchmark lending rate on Wednesday."
    content2 = "WASHINGTON (AP) — The Federal Reserve maintained its benchmark lending rate on Wednesday."

    is_syndicated, reason = SyndicationDetector.is_syndicated_copy(
        title1=title1,
        title2=title2,
        content1=content1,
        content2=content2,
    )
    assert is_syndicated
    assert "Identical title" in reason or "wire" in reason or "similarity" in reason

    # Source independence counting: 5 websites printing the same AP wire copy
    domains = ["chicagotribune.com", "denverpost.com", "baltimoresun.com", "orlandosentinel.com", "reuters.com"]
    groups = ["AP_WIRE", "AP_WIRE", "AP_WIRE", "AP_WIRE", None]
    independent_count = SyndicationDetector.calculate_independent_source_count(domains, groups)
    # 1 from AP_WIRE group + 1 from independent reuters.com = 2
    assert independent_count == 2


# =============================================================================
# 11. Source Health & Staleness Tests
# =============================================================================
def test_source_health_calculation():
    # Healthy source (high success rate)
    status_h, score_h = RobustIngestionService.calculate_source_health(
        success_count=95, failure_count=5, last_success_at=datetime.now(timezone.utc)
    )
    assert status_h == "HEALTHY"
    assert score_h >= 0.90

    # Failing source (high failure rate)
    status_f, score_f = RobustIngestionService.calculate_source_health(
        success_count=2, failure_count=20, last_success_at=None
    )
    assert status_f == "FAILING"

    # Robots blocked
    status_b, _ = RobustIngestionService.calculate_source_health(
        success_count=10, failure_count=0, last_success_at=None, robots_status="BLOCKED"
    )
    assert status_b == "BLOCKED"


# =============================================================================
# 12. Extractor Registry Tests
# =============================================================================
def test_source_extractor_registry():
    registry = ExtractorRegistry()

    class CustomBbcExtractor(BaseSourceExtractor):
        def matches_domain(self, url: str) -> bool:
            return "bbc.com" in url
        def extract(self, html: str, source_url: str) -> ExtractedArticleData:
            return ExtractedArticleData(url=source_url, title="BBC Custom Extracted")

    registry.register("bbc.com", CustomBbcExtractor())

    # Registered domain returns custom extractor
    bbc_ext = registry.get_extractor("https://www.bbc.com/news/uk-12345")
    assert isinstance(bbc_ext, CustomBbcExtractor)

    # Unregistered domain falls back to GenericSourceExtractor
    generic_ext = registry.get_extractor("https://randomnews.org/post/1")
    assert isinstance(generic_ext, GenericSourceExtractor)


# =============================================================================
# 13. Realistic 10-Item Feed Test (8 Valid, 1 Duplicate, 1 Invalid) & Failure Isolation
# =============================================================================
@pytest.mark.asyncio
async def test_realistic_feed_and_source_isolation(db_session: AsyncSession, monkeypatch):
    # Setup source and feed
    source = NewsSource(
        name="Global Tribune",
        slug=f"global-tribune-test-{datetime.now().timestamp()}",
        website_url="https://globaltribune.mock",
        domain="globaltribune.mock",
        health_status="HEALTHY",
    )
    db_session.add(source)
    await db_session.flush()

    feed = NewsFeed(
        name="Global Tribune Tech",
        feed_url="https://globaltribune.mock/feed.xml",
        source_id=source.id,
        is_active=True,
    )
    db_session.add(feed)
    await db_session.flush()

    # Pre-seed 1 existing article (the duplicate)
    dup_art = Article(
        title="Existing Story Headline",
        slug=f"existing-story-headline-{datetime.now().timestamp()}",
        canonical_url="https://globaltribune.mock/news/story-2",
        source_url="https://globaltribune.mock/news/story-2",
        content="Already indexed content.",
        source_id=source.id,
        feed_id=feed.id,
        status="PUBLISHED",
    )
    db_session.add(dup_art)
    await db_session.commit()

    # Mock XML with 10 items: 8 new valid, 1 duplicate (story-2), 1 invalid (no link)
    xml_items = ""
    for i in range(1, 11):
        if i == 2:
            link = "https://globaltribune.mock/news/story-2"
            title = "Existing Story Headline"
        elif i == 10:
            link = ""  # Invalid item with no link
            title = "Invalid Item"
        else:
            link = f"https://globaltribune.mock/news/story-{i}"
            title = f"Valid News Story Number {i}"
        
        xml_items += f"""
        <item>
            <title>{title}</title>
            <link>{link}</link>
            <description>Full informative paragraph description for story {i}.</description>
            <pubDate>Wed, 07 Oct 2026 10:00:00 GMT</pubDate>
        </item>
        """

    mock_rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Global Tribune Tech</title>
            <link>https://globaltribune.mock</link>
            <description>Technology news feed</description>
            {xml_items}
        </channel>
    </rss>
    """

    class MockFetcher:
        async def fetch_safe(self, url, **kwargs):
            return FetchResponse(
                html=mock_rss_xml,
                final_url=url,
                status_code=200,
                etag='"etag-xyz"',
            )

    service = RobustIngestionService(
        session=db_session,
        fetcher=MockFetcher(),
    )

    stats = await service.ingest_feed(feed)

    # 10 processed: 8 created, 1 duplicate, 0 pipeline crash
    assert stats["items_processed"] == 10
    assert stats["items_created"] == 8
    assert stats["duplicates"] == 1
    assert stats["status"] == "SUCCESS"


# =============================================================================
# 14. Web Intelligence API Endpoints Tests
# =============================================================================
@pytest.mark.asyncio
async def test_extraction_diagnostic_api(monkeypatch):
    from httpx import ASGITransport
    from app.main import app

    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Diagnostics Reveal New Physics Insight</title>
        <meta property="og:title" content="AI Diagnostics Reveal New Physics Insight" />
        <meta property="og:description" content="Machine learning models simulate complex fluid dynamics." />
        <link rel="canonical" href="https://sciencedaily.mock/physics-ai" />
    </head>
    <body>
        <article>
            <p>Researchers applied deep graph neural networks to turbulent fluid boundary layers.</p>
            <p>The resulting simulations uncovered coherent vortex structures previously undetected in wind tunnel tests.</p>
            <p>Aerospace manufacturers are already evaluating the findings for hypersonic wing geometry design.</p>
        </article>
    </body>
    </html>
    """

    async def mock_fetch_safe(self, url, **kwargs):
        return FetchResponse(
            html=sample_html,
            final_url="https://sciencedaily.mock/physics-ai",
            status_code=200,
            etag='"sci-123"',
        )

    monkeypatch.setattr(WebPageFetcher, "fetch_safe", mock_fetch_safe)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/extraction/test",
            json={"url": "https://sciencedaily.mock/physics-ai?utm_source=reddit"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["extraction_status"] == "SUCCESS"
        assert data["canonical_url"] == "https://sciencedaily.mock/physics-ai"
        assert data["quality_score"] > 0.60
        assert data["is_safe"] is True

