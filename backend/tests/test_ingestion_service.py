import os
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from unittest.mock import AsyncMock, patch

from app.database.session import AsyncSessionLocal
from app.models.source import NewsSource
from app.models.feed import NewsFeed
from app.models.article import Article
from app.models.topic import Topic
from app.models.ingestion_run import IngestionRun
from app.ingestion.rss.fetcher import RSSFetcher, FeedFetchError
from app.ingestion.services.ingestion_service import IngestionService

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def read_fixture(filename: str) -> str:
    with open(os.path.join(FIXTURES_DIR, filename), "r", encoding="utf-8") as f:
        return f.read()


@pytest.mark.asyncio
async def test_network_failure_handling():
    """Test 4: Fetcher handles network failures gracefully and raises FeedFetchError"""
    fetcher = RSSFetcher(timeout=2)
    with pytest.raises(FeedFetchError) as exc_info:
        await fetcher.fetch_feed("https://invalid-non-existent-domain-xyz-12345.org/rss.xml")
    assert "error" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_ingest_feed_new_articles_and_topic_mapping():
    """Test 13, 16, 17, 18: Ingestion creates articles, attaches topics, marks status, logs run"""
    async with AsyncSessionLocal() as session:
        # Create Topic
        topic_slug = f"tech-test-{uuid.uuid4().hex[:6]}"
        topic = Topic(name="Tech Test Topic", slug=topic_slug)
        session.add(topic)
        await session.flush()

        # Create Source & Feed
        source = NewsSource(
            id=uuid.uuid4(),
            name="Test Publisher",
            slug=f"test-pub-{uuid.uuid4().hex[:6]}",
            website_url="https://testpub.example.com",
        )
        session.add(source)
        await session.flush()

        feed = NewsFeed(
            id=uuid.uuid4(),
            source_id=source.id,
            name="Test RSS Feed",
            feed_url=f"https://testpub.example.com/rss-{uuid.uuid4().hex[:6]}.xml",
            feed_type="RSS",
            default_topic_id=topic.id,
            is_active=True,
        )
        session.add(feed)
        await session.commit()

        # Mock fetcher to return sample_rss.xml with unique run token
        run_token = uuid.uuid4().hex[:8]
        sample_xml = (
            read_fixture("sample_rss.xml")
            .replace("techuniverse.example.com", f"tech-{run_token}.example.com")
            .replace("Next-Gen Quantum", f"Next-Gen Quantum {run_token}")
            .replace("Autonomous Systems", f"Autonomous Systems {run_token}")
        )
        parsed = RSSFetcher.parse_xml_string(sample_xml)

        mock_fetcher = AsyncMock(spec=RSSFetcher)
        mock_fetcher.fetch_feed.return_value = parsed

        ingestion_service = IngestionService(session=session, fetcher=mock_fetcher)
        result = await ingestion_service.ingest_feed(feed.id)

        try:
            # Result checks
            assert result["fetched"] == 2
            assert result["new_articles"] == 2
            assert result["duplicates"] == 0
            assert result["failed"] == 0
            assert result["status"] == "SUCCESS"

            # Verify articles in DB
            stmt_arts = (
                select(Article)
                .options(selectinload(Article.topics))
                .where(Article.feed_id == feed.id)
            )
            res_arts = await session.execute(stmt_arts)
            articles = list(res_arts.scalars().all())
            assert len(articles) == 2

            for a in articles:
                assert a.status == "PUBLISHED"
                assert a.ingestion_method == "RSS"
                assert a.is_full_text_available is False
                assert a.source_id == source.id
                assert len(a.topics) == 1
                assert a.topics[0].id == topic.id

            # Verify IngestionRun record
            stmt_run = select(IngestionRun).where(IngestionRun.feed_id == feed.id)
            res_run = await session.execute(stmt_run)
            run = res_run.scalar_one_or_none()
            assert run is not None
            assert run.status == "SUCCESS"
            assert run.articles_created == 2
            assert run.finished_at is not None
        finally:
            # Clean up
            await session.execute(delete(Article).where(Article.feed_id == feed.id))
            await session.delete(feed)
            await session.delete(source)
            await session.delete(topic)
            await session.commit()


@pytest.mark.asyncio
async def test_failed_feed_does_not_stop_others():
    """Test 14, 15: Ingesting multiple feeds where one fails continues others"""
    async with AsyncSessionLocal() as session:
        source = NewsSource(
            id=uuid.uuid4(),
            name="Multi Publisher",
            slug=f"multi-pub-{uuid.uuid4().hex[:6]}",
            website_url="https://multipub.example.com",
        )
        session.add(source)
        await session.flush()

        feed_good = NewsFeed(
            id=uuid.uuid4(),
            source_id=source.id,
            name="Working Feed",
            feed_url=f"https://working-{uuid.uuid4().hex[:6]}.example.com/rss.xml",
            is_active=True,
        )
        feed_bad = NewsFeed(
            id=uuid.uuid4(),
            source_id=source.id,
            name="Broken Feed",
            feed_url=f"https://broken-{uuid.uuid4().hex[:6]}.example.com/rss.xml",
            is_active=True,
        )
        session.add_all([feed_good, feed_bad])
        await session.commit()

        run_token = uuid.uuid4().hex[:8]
        sample_xml = (
            read_fixture("sample_atom.xml")
            .replace("aiscience.example.com", f"aiscience-{run_token}.example.com")
            .replace("Sparse Attention", f"Sparse Attention {run_token}")
        )
        parsed_good = RSSFetcher.parse_xml_string(sample_xml)

        mock_fetcher = AsyncMock(spec=RSSFetcher)

        async def mock_fetch(url: str):
            if "broken" in url:
                raise FeedFetchError("Connection timed out on broken feed")
            return parsed_good

        mock_fetcher.fetch_feed.side_effect = mock_fetch

        ingestion_service = IngestionService(session=session, fetcher=mock_fetcher)

        try:
            # Ingest broken feed
            res_bad = await ingestion_service.ingest_feed(feed_bad.id)
            assert res_bad["status"] == "FAILED"
            assert res_bad["failed"] > 0
            assert "timed out" in (res_bad["error_message"] or "")

            # Ingest good feed
            res_good = await ingestion_service.ingest_feed(feed_good.id)
            assert res_good["status"] == "SUCCESS"
            assert res_good["new_articles"] == 1
        finally:
            await session.execute(delete(Article).where(Article.feed_id.in_([feed_good.id, feed_bad.id])))
            await session.delete(feed_good)
            await session.delete(feed_bad)
            await session.delete(source)
            await session.commit()

