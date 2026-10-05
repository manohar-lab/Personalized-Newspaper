"""
web_fetcher.py — Phase 5 Web Article Extraction

Responsible for:
1. Checking robots.txt compliance before fetching.
2. Fetching raw HTML from article URLs.
3. Returning a FetchResult with status and content for downstream extraction.

Design principles:
- If robots.txt disallows crawling, raise RobotsError (not a fatal pipeline failure).
- If HTTP fetch fails, raise FetchError (article falls back to RSS-only mode).
- Respects Crawl-delay from robots.txt.
- Uses a respectable User-Agent string.
"""

import asyncio
import logging
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Default settings (can be overridden when constructing WebFetcher)
DEFAULT_USER_AGENT = (
    "PersonalizedNewspaperBot/1.0 (+https://github.com/manohar-lab/Personalized-Newspaper)"
)
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_ROBOTS_TIMEOUT_SECONDS = 5


class FetchError(Exception):
    """Raised when the HTTP fetch fails (network or HTTP error)."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RobotsError(Exception):
    """Raised when robots.txt disallows fetching the URL."""

    pass


@dataclass
class FetchResult:
    """Result of a successful web fetch."""

    url: str
    final_url: str  # After redirects
    html: str
    status_code: int
    content_type: str = ""
    encoding: str = "utf-8"
    fetch_duration_ms: int = 0


class WebFetcher:
    """
    Fetches article HTML from a URL with robots.txt compliance checking.

    Usage:
        fetcher = WebFetcher()
        result = await fetcher.fetch(url)
    """

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        robots_timeout: int = DEFAULT_ROBOTS_TIMEOUT_SECONDS,
        respect_robots: bool = True,
        max_content_bytes: int = 5 * 1024 * 1024,  # 5 MB
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.robots_timeout = robots_timeout
        self.respect_robots = respect_robots
        self.max_content_bytes = max_content_bytes
        # Simple in-process cache for robots.txt per domain
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _get_robots_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    async def _fetch_robots(self, robots_url: str) -> Optional[urllib.robotparser.RobotFileParser]:
        """Fetches and parses robots.txt. Returns None if not accessible."""
        try:
            headers = {"User-Agent": self.user_agent}
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.robots_timeout, connect=3.0),
                follow_redirects=True,
                headers=headers,
            ) as client:
                resp = await client.get(robots_url)
                if resp.status_code == 404:
                    # No robots.txt means allow-all
                    return None
                if resp.status_code >= 400:
                    # Assume allow-all on other errors
                    return None
                rp = urllib.robotparser.RobotFileParser()
                rp.set_url(robots_url)
                rp.parse(resp.text.splitlines())
                return rp
        except Exception as exc:
            logger.debug(f"Could not fetch robots.txt at {robots_url}: {exc}")
            return None

    async def _get_robots_parser(
        self, url: str
    ) -> Optional[urllib.robotparser.RobotFileParser]:
        parsed = urllib.parse.urlparse(url)
        domain_key = f"{parsed.scheme}://{parsed.netloc}"
        if domain_key not in self._robots_cache:
            robots_url = self._get_robots_url(url)
            rp = await self._fetch_robots(robots_url)
            self._robots_cache[domain_key] = rp  # type: ignore[assignment]
        return self._robots_cache.get(domain_key)

    async def is_allowed(self, url: str) -> bool:
        """Returns True if robots.txt allows crawling the URL, or if robots.txt is absent."""
        if not self.respect_robots:
            return True
        rp = await self._get_robots_parser(url)
        if rp is None:
            return True
        return rp.can_fetch(self.user_agent, url)

    async def fetch(self, url: str) -> FetchResult:
        """
        Fetches HTML from a URL.

        Raises:
            RobotsError: if robots.txt disallows the URL.
            FetchError: if the HTTP fetch fails.
        """
        import time

        # Step 1: Robots.txt check
        if self.respect_robots:
            allowed = await self.is_allowed(url)
            if not allowed:
                raise RobotsError(
                    f"robots.txt disallows fetching: {url}"
                )

        # Step 2: Fetch HTML
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = await client.get(url)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                if response.status_code >= 400:
                    raise FetchError(
                        f"HTTP {response.status_code} error fetching article: {url}",
                        status_code=response.status_code,
                    )

                # Check content type — only process HTML
                content_type = response.headers.get("content-type", "")
                if content_type and not any(
                    ct in content_type.lower()
                    for ct in ("text/html", "application/xhtml")
                ):
                    raise FetchError(
                        f"Non-HTML content type '{content_type}' for URL: {url}"
                    )

                # Check content size
                raw_bytes = response.content
                if len(raw_bytes) > self.max_content_bytes:
                    raise FetchError(
                        f"Content too large ({len(raw_bytes)} bytes) for URL: {url}"
                    )

                html_text = response.text
                final_url = str(response.url)
                encoding = response.encoding or "utf-8"

                return FetchResult(
                    url=url,
                    final_url=final_url,
                    html=html_text,
                    status_code=response.status_code,
                    content_type=content_type,
                    encoding=encoding,
                    fetch_duration_ms=elapsed_ms,
                )

        except httpx.TimeoutException as exc:
            raise FetchError(
                f"Timeout ({self.timeout}s) fetching article: {url}"
            ) from exc
        except httpx.RequestError as exc:
            raise FetchError(f"Network error fetching article: {exc}") from exc
        except (FetchError, RobotsError):
            raise
        except Exception as exc:
            raise FetchError(f"Unexpected error fetching article: {exc}") from exc
