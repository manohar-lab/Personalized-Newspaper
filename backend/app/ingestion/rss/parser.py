import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any
import feedparser
from app.ingestion.rss.normalizer import ArticleNormalizer, NormalizedArticle

logger = logging.getLogger(__name__)


class RSSParser:
    def __init__(self, normalizer: Optional[ArticleNormalizer] = None):
        self.normalizer = normalizer or ArticleNormalizer()

    def parse_feed_metadata(self, parsed_feed: feedparser.FeedParserDict) -> Dict[str, Any]:
        feed_header = getattr(parsed_feed, "feed", {})
        return {
            "title": self.normalizer.clean_text(getattr(feed_header, "title", None) or feed_header.get("title")),
            "description": self.normalizer.clean_text(
                getattr(feed_header, "description", None)
                or feed_header.get("description")
                or getattr(feed_header, "subtitle", None)
                or feed_header.get("subtitle")
            ),
            "link": getattr(feed_header, "link", None) or feed_header.get("link"),
            "language": getattr(feed_header, "language", None) or feed_header.get("language") or "en",
        }

    def parse_entries(
        self,
        parsed_feed: feedparser.FeedParserDict,
        source_name: Optional[str] = None,
        feed_name: Optional[str] = None,
        language: str = "en",
        retrieval_time: Optional[datetime] = None,
    ) -> List[NormalizedArticle]:
        if retrieval_time is None:
            retrieval_time = datetime.now(timezone.utc)

        normalized_articles: List[NormalizedArticle] = []
        entries = getattr(parsed_feed, "entries", [])

        for idx, entry in enumerate(entries):
            try:
                norm_art = self.normalizer.normalize_entry(
                    entry=entry,
                    source_name=source_name,
                    feed_name=feed_name,
                    language=language,
                    retrieval_time=retrieval_time,
                )
                if norm_art:
                    normalized_articles.append(norm_art)
                else:
                    logger.debug(f"Skipped invalid feed entry at index {idx}")
            except Exception as exc:
                logger.warning(f"Error parsing entry index {idx}: {exc}")
                continue

        return normalized_articles
