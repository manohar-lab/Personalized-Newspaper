import os
from datetime import datetime, timezone
import pytest
from app.ingestion.rss.normalizer import ArticleNormalizer, NormalizedArticle
from app.ingestion.rss.parser import RSSParser
from app.ingestion.rss.fetcher import RSSFetcher, FeedFetchError

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def read_fixture(filename: str) -> str:
    with open(os.path.join(FIXTURES_DIR, filename), "r", encoding="utf-8") as f:
        return f.read()


def test_rss_parser_standard():
    """Test 1: RSS 2.0 parser extracting entries, authors, media, dates"""
    xml = read_fixture("sample_rss.xml")
    parsed = RSSFetcher.parse_xml_string(xml)
    parser = RSSParser()

    meta = parser.parse_feed_metadata(parsed)
    assert meta["title"] == "Tech Universe Feed"
    assert "technology innovations" in meta["description"]

    articles = parser.parse_entries(parsed, source_name="Tech Universe", feed_name="Tech Feed")
    assert len(articles) == 2

    # Article 1 checks
    art1 = articles[0]
    assert art1.title == "Next-Gen Quantum Processing Unit Achieves Superconducting Milestone"
    assert art1.author == "Dr. Elena Rostova"
    assert art1.image_url == "https://techuniverse.example.com/images/quantum.jpg"
    assert art1.source_name == "Tech Universe"
    assert art1.published_at.year == 2026
    assert art1.published_at.month == 10
    assert art1.published_at.day == 5
    # UTM parameter and fragment stripped in canonical_url
    assert "utm_source" not in (art1.canonical_url or "")
    assert "#comments" not in (art1.canonical_url or "")
    assert art1.canonical_url == "https://techuniverse.example.com/articles/quantum-breakthrough"

    # Article 2 checks
    art2 = articles[1]
    assert art2.title == "Autonomous Systems Adopt Lightweight Embedded Vision Models"
    assert "Alex Chen" in (art2.author or "")
    assert art2.image_url == "https://techuniverse.example.com/images/tinyml.png"


def test_atom_parser():
    """Test 2: Atom 1.0 parser extracting entries, summary, and dates"""
    xml = read_fixture("sample_atom.xml")
    parsed = RSSFetcher.parse_xml_string(xml)
    parser = RSSParser()

    articles = parser.parse_entries(parsed, source_name="AI Science", feed_name="AI Dispatch")
    assert len(articles) == 1

    art = articles[0]
    assert art.title == "Sparse Attention Mechanisms Yield 10x Efficiency in Long-Context Reasoning"
    assert art.author == "Sarah Jenkins"
    assert "hierarchical sparse block architectures" in (art.description or "")
    assert "utm_campaign" not in (art.canonical_url or "")
    assert art.canonical_url == "https://aiscience.example.com/posts/sparse-attention"


def test_missing_fields_in_rss():
    """Test 5, 6, 7, 8: Missing title, author, image, pubDate"""
    xml = read_fixture("missing_fields_rss.xml")
    parsed = RSSFetcher.parse_xml_string(xml)
    parser = RSSParser()

    retrieval_time = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
    articles = parser.parse_entries(
        parsed,
        source_name="Minimal",
        feed_name="Minimal Feed",
        retrieval_time=retrieval_time,
    )

    # Missing title and missing link entries must be filtered out
    assert len(articles) == 1

    art = articles[0]
    assert art.title == "Autonomous Drones Complete Arctic Mapping Mission"
    # Missing author is None
    assert art.author is None
    # Missing image is None
    assert art.image_url is None
    # Missing pub date fallbacks to retrieval_time
    assert art.published_at == retrieval_time


def test_date_normalization():
    """Test 9: Date normalization with RFC 822, ISO 8601, timezone offsets"""
    # RFC 822 GMT
    dt1 = ArticleNormalizer.normalize_date("Mon, 05 Oct 2026 04:00:00 GMT")
    assert dt1.tzinfo is not None
    assert dt1.hour == 4

    # ISO 8601 with offset +05:30 -> converts to UTC (hour 4 - 5.5 = 22:30 previous day)
    dt2 = ArticleNormalizer.normalize_date("2026-10-05T04:00:00+05:30")
    assert dt2.tzinfo is not None
    assert dt2.hour == 22
    assert dt2.day == 4

    # Missing date with fallback
    fallback = datetime(2026, 10, 5, 8, 0, 0, tzinfo=timezone.utc)
    dt3 = ArticleNormalizer.normalize_date(None, fallback_time=fallback)
    assert dt3 == fallback


def test_url_normalization():
    """Test 10: URL normalization (stripping tracking params, fragments, trailing slashes)"""
    url1 = "https://example.com/news/article-one/?utm_source=twitter&utm_medium=social&utm_campaign=launch#comments"
    norm1 = ArticleNormalizer.normalize_url(url1)
    assert norm1 == "https://example.com/news/article-one"

    url2 = "http://EXAMPLE.COM:80/path/to/story?fbclid=12345&id=99"
    norm2 = ArticleNormalizer.normalize_url(url2)
    assert norm2 == "http://example.com/path/to/story?id=99"

    # None / Empty url
    assert ArticleNormalizer.normalize_url(None) is None
    assert ArticleNormalizer.normalize_url("") is None


def test_content_hash_consistency():
    """Content hash calculation is deterministic and stable"""
    h1 = ArticleNormalizer.compute_content_hash("New AI Model Released", "https://example.com/ai", "Description here")
    h2 = ArticleNormalizer.compute_content_hash("New AI Model Released", "https://example.com/ai", "Description here")
    h3 = ArticleNormalizer.compute_content_hash("Different Title", "https://example.com/ai", "Description here")

    assert h1 == h2
    assert h1 != h3
