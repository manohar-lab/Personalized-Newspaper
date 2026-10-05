import logging
from typing import Optional, Any
import httpx
import feedparser
from app.core.config import settings

logger = logging.getLogger(__name__)


class FeedFetchError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RSSFetcher:
    def __init__(
        self,
        timeout: Optional[int] = None,
        user_agent: Optional[str] = None,
    ):
        self.timeout = timeout or settings.FEED_FETCH_TIMEOUT_SECONDS
        self.user_agent = user_agent or settings.USER_AGENT

    async def fetch_feed_xml(self, feed_url: str) -> str:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = await client.get(feed_url)
                if response.status_code >= 400:
                    raise FeedFetchError(
                        f"HTTP {response.status_code} error fetching feed: {feed_url}",
                        status_code=response.status_code,
                    )
                return response.text
        except httpx.TimeoutException as exc:
            logger.warning(f"Timeout fetching feed URL '{feed_url}': {exc}")
            raise FeedFetchError(f"Connection timed out after {self.timeout}s: {feed_url}")
        except httpx.RequestError as exc:
            logger.warning(f"Network error fetching feed URL '{feed_url}': {exc}")
            raise FeedFetchError(f"Network error fetching feed: {str(exc)}")
        except Exception as exc:
            if isinstance(exc, FeedFetchError):
                raise
            logger.error(f"Unexpected error fetching feed URL '{feed_url}': {exc}")
            raise FeedFetchError(f"Unexpected fetch error: {str(exc)}")

    async def fetch_feed(self, feed_url: str) -> feedparser.FeedParserDict:
        xml_content = await self.fetch_feed_xml(feed_url)
        parsed = feedparser.parse(xml_content)
        if getattr(parsed, "bozo", 0) == 1 and not parsed.entries:
            bozo_exc = getattr(parsed, "bozo_exception", None)
            raise FeedFetchError(f"Malformed or empty feed content: {bozo_exc or 'Unknown parsing error'}")
        return parsed

    @staticmethod
    def parse_xml_string(xml_content: str) -> feedparser.FeedParserDict:
        return feedparser.parse(xml_content)
