import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import AsyncSessionLocal
from app.models.article import Article
from app.models.source import NewsSource
from app.ingestion.rss.normalizer import NormalizedArticle, ArticleNormalizer
from app.ingestion.deduplication.article_deduplicator import ArticleDeduplicator


@pytest.mark.asyncio
async def test_article_deduplication_exact_url():
    """Test 11: Duplicate URL detection (canonical URL / source URL)"""
    async with AsyncSessionLocal() as session:
        existing_url = f"https://dedupe.example.com/story-{uuid.uuid4().hex[:6]}"
        content_hash = ArticleNormalizer.compute_content_hash("Unique Headline", existing_url)

        art = Article(
            id=uuid.uuid4(),
            title="Unique Headline",
            slug=f"unique-headline-{uuid.uuid4().hex[:6]}",
            source_url=existing_url,
            canonical_url=existing_url,
            content_hash=content_hash,
            published_at=datetime.now(timezone.utc),
            status="PUBLISHED",
            ingestion_method="RSS",
        )
        session.add(art)
        await session.commit()

        try:
            candidate = NormalizedArticle(
                title="Another Headline Name",
                url=existing_url,
                canonical_url=existing_url,
                published_at=datetime.now(timezone.utc),
                content_hash=ArticleNormalizer.compute_content_hash("Another Headline Name", existing_url),
            )

            is_dupe, reason = await ArticleDeduplicator.is_duplicate(session, candidate)
            assert is_dupe is True
            assert reason == "duplicate_url"
        finally:
            await session.delete(art)
            await session.commit()


@pytest.mark.asyncio
async def test_article_deduplication_content_hash():
    """Test 12: Duplicate content hash detection"""
    async with AsyncSessionLocal() as session:
        unique_url = f"https://hash.example.com/story-{uuid.uuid4().hex[:6]}"
        c_hash = f"hash-{uuid.uuid4().hex}"

        art = Article(
            id=uuid.uuid4(),
            title="Hash Test Headline",
            slug=f"hash-test-{uuid.uuid4().hex[:6]}",
            source_url=unique_url,
            canonical_url=unique_url,
            content_hash=c_hash,
            published_at=datetime.now(timezone.utc),
            status="PUBLISHED",
            ingestion_method="RSS",
        )
        session.add(art)
        await session.commit()

        try:
            candidate = NormalizedArticle(
                title="Some variation",
                url=f"https://other.example.com/story-{uuid.uuid4().hex[:6]}",
                canonical_url=f"https://other.example.com/story-{uuid.uuid4().hex[:6]}",
                published_at=datetime.now(timezone.utc),
                content_hash=c_hash,
            )

            is_dupe, reason = await ArticleDeduplicator.is_duplicate(session, candidate)
            assert is_dupe is True
            assert reason == "duplicate_content_hash"
        finally:
            await session.delete(art)
            await session.commit()


@pytest.mark.asyncio
async def test_unique_article_not_duplicated():
    """Unique article passes deduplication successfully"""
    async with AsyncSessionLocal() as session:
        candidate = NormalizedArticle(
            title=f"Brand New Story {uuid.uuid4().hex[:8]}",
            url=f"https://brandnew.example.com/{uuid.uuid4().hex}",
            canonical_url=f"https://brandnew.example.com/{uuid.uuid4().hex}",
            published_at=datetime.now(timezone.utc),
            content_hash=f"new-hash-{uuid.uuid4().hex}",
        )

        is_dupe, reason = await ArticleDeduplicator.is_duplicate(session, candidate)
        assert is_dupe is False
        assert reason is None
