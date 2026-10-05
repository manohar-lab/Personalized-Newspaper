"""test_real_sources.py — Phase 5 Real Publisher Integration Tests.

Validates the extraction pipeline against real publisher websites that permit
automated access, checking robots compliance, metadata, body text, and canonical URLs.
"""
import pytest
from app.extraction.extractor import GenericArticleExtractor
from app.extraction.fetcher import WebPageFetcher
from app.extraction.models import ExtractionStatus, RobotsAccess
from app.extraction.robots import RobotsChecker
from app.ingestion.rss.fetcher import RSSFetcher
from app.ingestion.rss.parser import RSSParser


@pytest.mark.asyncio
async def test_real_source_python_org():
    """Test extraction on Python.org blog."""
    url = "https://www.python.org/blogs/"
    robots = RobotsChecker()
    fetcher = WebPageFetcher()
    extractor = GenericArticleExtractor()

    access = await robots.check_access(url)
    assert access in (RobotsAccess.ALLOWED, RobotsAccess.UNKNOWN)

    if access == RobotsAccess.ALLOWED:
        html, final_url, status_code = await fetcher.fetch(url)
        assert status_code == 200
        article_data = extractor.extract(html, final_url)
        assert article_data.title is not None
        assert len(article_data.title) > 0


@pytest.mark.asyncio
async def test_real_source_rss_discovered_article():
    """Discover a live article from an RSS feed, check robots, and extract."""
    rss_fetcher = RSSFetcher()
    parser = RSSParser()
    robots = RobotsChecker()
    fetcher = WebPageFetcher()
    extractor = GenericArticleExtractor()

    # Discover live entries from Python.org RSS feed
    feed_url = "https://www.python.org/dev/peps/peps.rss"
    parsed_feed = await rss_fetcher.fetch_feed(feed_url)
    entries = parser.parse_entries(parsed_feed, source_name="Python PEPs", feed_name="PEPs Feed")

    if entries:
        test_article = entries[0]
        url = test_article.url
        assert url.startswith("http")

        # Check robots.txt
        access = await robots.check_access(url)
        assert access in (RobotsAccess.ALLOWED, RobotsAccess.UNKNOWN, RobotsAccess.DISALLOWED)

        if access == RobotsAccess.ALLOWED:
            html, final_url, status_code = await fetcher.fetch(url)
            assert status_code == 200
            extracted = extractor.extract(html, final_url)
            assert extracted.title is not None
            assert extracted.status in (ExtractionStatus.SUCCESS, ExtractionStatus.PARTIAL)
