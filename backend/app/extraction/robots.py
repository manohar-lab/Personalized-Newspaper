"""robots.py — Phase 5 Robots.txt Compliance Checking.

Fetches and caches publisher robots.txt files, verifying whether
automated extraction is permitted for the target URL.
"""
import logging
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import settings
from app.extraction.models import RobotsAccess

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Robots.txt compliance checker with in-memory caching."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        cache_ttl_seconds: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.user_agent = user_agent or settings.USER_AGENT
        self.cache_ttl_seconds = cache_ttl_seconds or settings.ROBOTS_CACHE_TTL_SECONDS
        self.timeout_seconds = timeout_seconds or 10
        # Cache format: domain -> (RobotFileParser, timestamp)
        self._cache: Dict[str, Tuple[Optional[RobotFileParser], float]] = {}

    def get_robots_url(self, target_url: str) -> Optional[str]:
        """Derive the robots.txt URL from a target URL."""
        try:
            parsed = urlparse(target_url)
            if not parsed.scheme or not parsed.netloc:
                return None
            return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        except Exception:
            return None

    def get_domain(self, target_url: str) -> Optional[str]:
        """Extract domain/netloc from URL."""
        try:
            parsed = urlparse(target_url)
            return parsed.netloc.lower()
        except Exception:
            return None

    async def _fetch_robots_txt(self, domain: str, robots_url: str) -> Optional[RobotFileParser]:
        """Fetch robots.txt for a domain and parse it."""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(response.text.splitlines())
                    return parser
                elif response.status_code in (401, 403):
                    # Disallow everything if robots.txt itself is forbidden
                    parser = RobotFileParser()
                    parser.parse(["User-agent: *", "Disallow: /"])
                    return parser
                elif response.status_code == 404:
                    # 404 means no robots.txt restrictions
                    parser = RobotFileParser()
                    parser.allow_all = True  # type: ignore[attr-defined]
                    return parser
                else:
                    return None
        except Exception as e:
            logger.debug(f"Failed to fetch robots.txt for {domain}: {e}")
            return None

    async def check_access(self, target_url: str) -> RobotsAccess:
        """Check whether fetching target_url is permitted by the publisher's robots.txt.
        
        Returns:
            RobotsAccess.ALLOWED: if explicitly allowed or no restriction
            RobotsAccess.DISALLOWED: if blocked by robots.txt
            RobotsAccess.UNKNOWN: if robots.txt could not be retrieved
        """
        domain = self.get_domain(target_url)
        robots_url = self.get_robots_url(target_url)

        if not domain or not robots_url:
            return RobotsAccess.ALLOWED

        now = time.time()
        # Check cache
        if domain in self._cache:
            parser, timestamp = self._cache[domain]
            if now - timestamp < self.cache_ttl_seconds:
                if parser is None:
                    return RobotsAccess.UNKNOWN
                if getattr(parser, "allow_all", False):
                    return RobotsAccess.ALLOWED
                can_fetch = parser.can_fetch(self.user_agent, target_url) or parser.can_fetch("*", target_url)
                return RobotsAccess.ALLOWED if can_fetch else RobotsAccess.DISALLOWED

        # Fetch and cache
        parser = await self._fetch_robots_txt(domain, robots_url)
        self._cache[domain] = (parser, now)

        if parser is None:
            # Network issue getting robots.txt -> return UNKNOWN (or default allow for non-intrusive access)
            return RobotsAccess.UNKNOWN

        if getattr(parser, "allow_all", False):
            return RobotsAccess.ALLOWED

        can_fetch = parser.can_fetch(self.user_agent, target_url) or parser.can_fetch("*", target_url)
        return RobotsAccess.ALLOWED if can_fetch else RobotsAccess.DISALLOWED
