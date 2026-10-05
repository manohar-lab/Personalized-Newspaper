import uuid
import asyncio
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import AsyncSessionLocal
from app.models.source import NewsSource
from app.models.feed import NewsFeed
from app.models.topic import Topic
from app.core.logging import logger

INITIAL_SOURCES_AND_FEEDS: List[Dict[str, Any]] = [
    {
        "name": "Ars Technica",
        "slug": "ars-technica",
        "website_url": "https://arstechnica.com",
        "description": "Original news and reviews of technology, science, and policy.",
        "logo_url": "https://cdn.arstechnica.net/wp-content/themes/ars/assets/img/ars-logo-open-grey.png",
        "feeds": [
            {
                "name": "Ars Technica Main Feed",
                "feed_url": "https://feeds.arstechnica.com/arstechnica/index",
                "feed_type": "RSS",
                "language": "en",
                "topic_slug": "technology",
            }
        ],
    },
    {
        "name": "The Verge",
        "slug": "the-verge",
        "website_url": "https://www.theverge.com",
        "description": "Covering the intersection of technology, science, art, and culture.",
        "logo_url": "https://www.theverge.com/icons/favicon.ico",
        "feeds": [
            {
                "name": "The Verge All Stories",
                "feed_url": "https://www.theverge.com/rss/index.xml",
                "feed_type": "RSS",
                "language": "en",
                "topic_slug": "technology",
            }
        ],
    },
    {
        "name": "TechCrunch",
        "slug": "techcrunch",
        "website_url": "https://techcrunch.com",
        "description": "Startup and technology news, funding, and artificial intelligence innovations.",
        "logo_url": "https://techcrunch.com/wp-content/uploads/2015/02/cropped-cropped-favicon-gradient.png",
        "feeds": [
            {
                "name": "TechCrunch Artificial Intelligence",
                "feed_url": "https://techcrunch.com/category/artificial-intelligence/feed/",
                "feed_type": "RSS",
                "language": "en",
                "topic_slug": "artificial-intelligence",
            }
        ],
    },
    {
        "name": "MIT Technology Review",
        "slug": "mit-technology-review",
        "website_url": "https://www.technologyreview.com",
        "description": "In-depth analysis of emerging technologies and artificial intelligence from MIT.",
        "logo_url": "https://www.technologyreview.com/favicon.ico",
        "feeds": [
            {
                "name": "MIT Tech Review AI",
                "feed_url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
                "feed_type": "RSS",
                "language": "en",
                "topic_slug": "artificial-intelligence",
            }
        ],
    },
    {
        "name": "ScienceDaily",
        "slug": "sciencedaily",
        "website_url": "https://www.sciencedaily.com",
        "description": "Breaking science news and research articles from universities and research centers.",
        "logo_url": "https://www.sciencedaily.com/favicon.ico",
        "feeds": [
            {
                "name": "ScienceDaily Top Headlines",
                "feed_url": "https://www.sciencedaily.com/rss/top/science.xml",
                "feed_type": "RSS",
                "language": "en",
                "topic_slug": "science",
            }
        ],
    },
    {
        "name": "Phys.org",
        "slug": "phys-org",
        "website_url": "https://phys.org",
        "description": "Physics, space exploration, nanotechnology, and general science updates.",
        "logo_url": "https://phys.org/favicon.ico",
        "feeds": [
            {
                "name": "Phys.org Spotlight News",
                "feed_url": "https://phys.org/rss-feed/",
                "feed_type": "RSS",
                "language": "en",
                "topic_slug": "science",
            }
        ],
    },
    {
        "name": "BBC News",
        "slug": "bbc-news",
        "website_url": "https://www.bbc.com/news",
        "description": "Global news, business reporting, and breaking international analysis.",
        "logo_url": "https://www.bbc.com/favicon.ico",
        "feeds": [
            {
                "name": "BBC World News",
                "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
                "feed_type": "RSS",
                "language": "en",
                "topic_slug": "world-news",
            },
            {
                "name": "BBC Business News",
                "feed_url": "https://feeds.bbci.co.uk/news/business/rss.xml",
                "feed_type": "RSS",
                "language": "en",
                "topic_slug": "business",
            },
        ],
    },
    {
        "name": "Wall Street Journal",
        "slug": "wall-street-journal",
        "website_url": "https://www.wsj.com",
        "description": "Business, finance, economic news, and global market coverage.",
        "logo_url": "https://www.wsj.com/favicon.ico",
        "feeds": [
            {
                "name": "WSJ US Business",
                "feed_url": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
                "feed_type": "RSS",
                "language": "en",
                "topic_slug": "business",
            }
        ],
    },
    {
        "name": "NPR",
        "slug": "npr",
        "website_url": "https://www.npr.org",
        "description": "Independent journalism, world affairs, and cultural reporting.",
        "logo_url": "https://www.npr.org/favicon.ico",
        "feeds": [
            {
                "name": "NPR News Headlines",
                "feed_url": "https://feeds.npr.org/1001/rss.xml",
                "feed_type": "RSS",
                "language": "en",
                "topic_slug": "world-news",
            }
        ],
    },
]


async def seed_sources_and_feeds(session: AsyncSession) -> Dict[str, int]:
    """
    Idempotent seeding function for news sources and RSS feeds.
    """
    # Cache topics for mapping
    stmt_topics = select(Topic)
    topics_res = await session.execute(stmt_topics)
    topic_map = {t.slug: t.id for t in topics_res.scalars().all()}

    sources_added = 0
    feeds_added = 0

    for src_data in INITIAL_SOURCES_AND_FEEDS:
        stmt_src = select(NewsSource).where(NewsSource.slug == src_data["slug"])
        res_src = await session.execute(stmt_src)
        source = res_src.scalar_one_or_none()

        if not source:
            source = NewsSource(
                id=uuid.uuid4(),
                name=src_data["name"],
                slug=src_data["slug"],
                website_url=src_data["website_url"],
                description=src_data.get("description"),
                logo_url=src_data.get("logo_url"),
                is_active=True,
            )
            session.add(source)
            await session.flush()
            sources_added += 1

        for feed_data in src_data["feeds"]:
            stmt_feed = select(NewsFeed).where(
                NewsFeed.feed_url == feed_data["feed_url"]
            )
            res_feed = await session.execute(stmt_feed)
            feed = res_feed.scalar_one_or_none()

            if not feed:
                topic_id = topic_map.get(feed_data.get("topic_slug", ""))
                feed = NewsFeed(
                    id=uuid.uuid4(),
                    source_id=source.id,
                    name=feed_data["name"],
                    feed_url=feed_data["feed_url"],
                    feed_type=feed_data.get("feed_type", "RSS"),
                    language=feed_data.get("language", "en"),
                    is_active=True,
                    default_topic_id=topic_id,
                )
                session.add(feed)
                feeds_added += 1

    if sources_added > 0 or feeds_added > 0:
        await session.commit()
        logger.info(
            f"Seeded {sources_added} sources and {feeds_added} feeds into the database."
        )
    else:
        logger.info("All sources and feeds already exist in the database.")

    return {"sources_added": sources_added, "feeds_added": feeds_added}


async def main():
    async with AsyncSessionLocal() as session:
        counts = await seed_sources_and_feeds(session)
        print(f"Seed complete: {counts}")


if __name__ == "__main__":
    asyncio.run(main())
