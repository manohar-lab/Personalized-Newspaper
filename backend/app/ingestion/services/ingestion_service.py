import re
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import NewsSource
from app.models.feed import NewsFeed
from app.models.article import Article
from app.models.topic import Topic
from app.models.ingestion_run import IngestionRun
from app.ingestion.rss.fetcher import RSSFetcher, FeedFetchError
from app.ingestion.rss.parser import RSSParser
from app.ingestion.rss.normalizer import ArticleNormalizer, NormalizedArticle
from app.ingestion.deduplication.article_deduplicator import ArticleDeduplicator

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:200]


class IngestionService:
    def __init__(
        self,
        session: AsyncSession,
        fetcher: Optional[RSSFetcher] = None,
        parser: Optional[RSSParser] = None,
        deduplicator: Optional[ArticleDeduplicator] = None,
    ):
        self.session = session
        self.fetcher = fetcher or RSSFetcher()
        self.parser = parser or RSSParser()
        self.deduplicator = deduplicator or ArticleDeduplicator()

    async def test_feed(self, feed_url: str) -> Dict[str, Any]:
        """
        Tests fetching and parsing a feed without saving any records into the database.
        """
        try:
            parsed_feed = await self.fetcher.fetch_feed(feed_url)
            meta = self.parser.parse_feed_metadata(parsed_feed)
            normalized_entries = self.parser.parse_entries(
                parsed_feed=parsed_feed,
                source_name=meta.get("title"),
                feed_name=meta.get("title"),
            )

            sample_entries = [
                {
                    "title": art.title,
                    "description": art.description,
                    "url": art.url,
                    "canonical_url": art.canonical_url,
                    "author": art.author,
                    "image_url": art.image_url,
                    "published_at": art.published_at,
                    "content_hash": art.content_hash,
                }
                for art in normalized_entries[:5]
            ]

            return {
                "feed_title": meta.get("title"),
                "feed_description": meta.get("description"),
                "feed_url": feed_url,
                "feed_type": "RSS",
                "entries_count": len(normalized_entries),
                "is_valid": True,
                "sample_entries": sample_entries,
                "error": None,
            }
        except Exception as exc:
            logger.warning(f"Feed test failed for {feed_url}: {exc}")
            return {
                "feed_title": None,
                "feed_description": None,
                "feed_url": feed_url,
                "feed_type": "UNKNOWN",
                "entries_count": 0,
                "is_valid": False,
                "sample_entries": [],
                "error": str(exc),
            }

    async def _generate_unique_slug(self, title: str) -> str:
        base_slug = slugify(title)
        if not base_slug:
            base_slug = "article"

        candidate = base_slug
        # Check if exists
        stmt = select(Article.id).where(Article.slug == candidate).limit(1)
        res = await self.session.execute(stmt)
        if res.scalar_one_or_none() is None:
            return candidate

        # Append short random hex
        short_id = uuid.uuid4().hex[:8]
        return f"{base_slug[:190]}-{short_id}"

    async def ingest_feed(self, feed_id: uuid.UUID) -> Dict[str, Any]:
        """
        Ingests a single feed:
        Fetch -> Parse -> Normalize -> Deduplicate -> Store -> Log Run
        """
        # 1. Fetch Feed from database
        stmt = (
            select(NewsFeed)
            .options(
                selectinload(NewsFeed.source),
                selectinload(NewsFeed.default_topic),
            )
            .where(NewsFeed.id == feed_id)
        )
        result = await self.session.execute(stmt)
        feed = result.scalar_one_or_none()

        if not feed:
            raise ValueError(f"NewsFeed with ID {feed_id} not found.")

        # 2. Create IngestionRun entry in database
        run_record = IngestionRun(
            id=uuid.uuid4(),
            feed_id=feed.id,
            started_at=datetime.now(timezone.utc),
            status="RUNNING",
            articles_fetched=0,
            articles_created=0,
            duplicates_found=0,
            errors_count=0,
        )
        self.session.add(run_record)
        await self.session.commit()

        fetched_count = 0
        created_count = 0
        duplicate_count = 0
        error_count = 0
        error_msg = None

        logger.info(f"Ingestion started for feed: '{feed.name}' ({feed.feed_url})")

        try:
            # 3. Fetch Feed
            parsed_feed = await self.fetcher.fetch_feed(feed.feed_url)

            # 4. Parse & Normalize
            source_name = feed.source.name if feed.source else feed.name
            normalized_articles = self.parser.parse_entries(
                parsed_feed=parsed_feed,
                source_name=source_name,
                feed_name=feed.name,
                language=feed.language,
            )
            fetched_count = len(normalized_articles)
            run_record.articles_fetched = fetched_count

            # Topic mapping from default_topic
            default_topic = feed.default_topic
            if not default_topic and feed.default_topic_id:
                stmt_topic = select(Topic).where(Topic.id == feed.default_topic_id)
                res_topic = await self.session.execute(stmt_topic)
                default_topic = res_topic.scalar_one_or_none()

            # 5. Process entries
            for norm_art in normalized_articles:
                try:
                    # Deduplication check
                    is_dupe, dupe_reason = await self.deduplicator.is_duplicate(
                        session=self.session,
                        article=norm_art,
                        source_id=feed.source_id,
                    )

                    if is_dupe:
                        duplicate_count += 1
                        continue

                    # Create new Article
                    slug = await self._generate_unique_slug(norm_art.title)
                    reading_time = max(
                        1,
                        len((norm_art.description or "").split()) // 150
                    ) if norm_art.description else 2

                    new_article = Article(
                        id=uuid.uuid4(),
                        title=norm_art.title,
                        slug=slug,
                        description=norm_art.description,
                        content=None,
                        source_id=feed.source_id,
                        feed_id=feed.id,
                        source_name=source_name,
                        source_url=norm_art.url,
                        canonical_url=norm_art.canonical_url,
                        ingestion_method="RSS",
                        author=norm_art.author,
                        image_url=norm_art.image_url,
                        published_at=norm_art.published_at,
                        reading_time_minutes=reading_time,
                        status="PUBLISHED",
                        content_hash=norm_art.content_hash,
                        language=feed.language,
                        is_full_text_available=False,
                    )

                    if default_topic:
                        new_article.topics.append(default_topic)

                    self.session.add(new_article)
                    created_count += 1
                    # Flush to make newly added article accessible for deduplication within the same batch
                    await self.session.flush()

                except Exception as entry_exc:
                    logger.warning(
                        f"Error saving entry '{norm_art.title}' from feed '{feed.name}': {entry_exc}"
                    )
                    error_count += 1

            # Update feed success state
            now = datetime.now(timezone.utc)
            feed.last_fetched_at = now
            feed.last_success_at = now
            feed.last_error = None

            # Update run state
            run_status = "SUCCESS"
            if error_count > 0 and created_count > 0:
                run_status = "PARTIAL"
            elif error_count > 0 and created_count == 0 and fetched_count > 0:
                run_status = "FAILED"

            run_record.status = run_status
            run_record.articles_created = created_count
            run_record.duplicates_found = duplicate_count
            run_record.errors_count = error_count
            run_record.finished_at = now

            await self.session.commit()

            logger.info(
                f"Ingestion completed for feed '{feed.name}': fetched={fetched_count}, "
                f"created={created_count}, duplicates={duplicate_count}, failed={error_count}"
            )

            return {
                "feed": feed.name,
                "feed_id": feed.id,
                "fetched": fetched_count,
                "new_articles": created_count,
                "duplicates": duplicate_count,
                "failed": error_count,
                "status": run_status,
                "error_message": None,
            }

        except Exception as feed_exc:
            now = datetime.now(timezone.utc)
            error_msg = str(feed_exc)
            logger.error(f"Ingestion failed for feed '{feed.name}': {error_msg}")

            feed.last_fetched_at = now
            feed.last_failure_at = now
            feed.last_error = error_msg

            run_record.status = "FAILED"
            run_record.articles_fetched = fetched_count
            run_record.articles_created = created_count
            run_record.duplicates_found = duplicate_count
            run_record.errors_count = error_count + 1
            run_record.error_message = error_msg
            run_record.finished_at = now

            await self.session.commit()

            return {
                "feed": feed.name,
                "feed_id": feed.id,
                "fetched": fetched_count,
                "new_articles": created_count,
                "duplicates": duplicate_count,
                "failed": error_count + 1,
                "status": "FAILED",
                "error_message": error_msg,
            }

    async def ingest_all_active_feeds(self) -> Dict[str, Any]:
        """
        Ingests all active news feeds. A failure in one feed will NOT stop others.
        """
        stmt = (
            select(NewsFeed)
            .where(NewsFeed.is_active == True)
            .order_by(NewsFeed.name)
        )
        result = await self.session.execute(stmt)
        active_feeds = list(result.scalars().all())

        results: List[Dict[str, Any]] = []
        total_fetched = 0
        total_created = 0
        total_duplicates = 0
        success_count = 0
        fail_count = 0

        logger.info(f"Starting batch ingestion for {len(active_feeds)} active feeds.")

        for feed in active_feeds:
            try:
                feed_res = await self.ingest_feed(feed.id)
                results.append(feed_res)
                total_fetched += feed_res["fetched"]
                total_created += feed_res["new_articles"]
                total_duplicates += feed_res["duplicates"]
                if feed_res["status"] in ("SUCCESS", "PARTIAL"):
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"Unexpected error ingesting feed {feed.id}: {e}")
                results.append(
                    {
                        "feed": feed.name,
                        "feed_id": feed.id,
                        "fetched": 0,
                        "new_articles": 0,
                        "duplicates": 0,
                        "failed": 1,
                        "status": "FAILED",
                        "error_message": str(e),
                    }
                )
                fail_count += 1

        return {
            "total_feeds": len(active_feeds),
            "successful_feeds": success_count,
            "failed_feeds": fail_count,
            "total_articles_fetched": total_fetched,
            "total_articles_created": total_created,
            "total_duplicates_found": total_duplicates,
            "results": results,
        }
