"""rate_limiter.py — Phase 20 Per-Domain Rate Limiting & Backpressure.

Coordinates request pacing on a per-domain basis, respecting HTTP 429 Retry-After
headers and preventing server overload.
"""
import asyncio
import logging
import time
from typing import Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DomainRateLimiter:
    """Async per-domain rate limiter."""

    def __init__(self, default_min_delay_seconds: float = 1.0):
        self.default_min_delay = default_min_delay_seconds
        self._last_access: Dict[str, float] = {}
        self._backoff_until: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url.strip())
            return (parsed.netloc or "").lower().split(":")[0]
        except Exception:
            return "unknown"

    async def _get_lock(self, domain: str) -> asyncio.Lock:
        async with self._global_lock:
            if domain not in self._locks:
                self._locks[domain] = asyncio.Lock()
            return self._locks[domain]

    async def acquire(self, url: str, custom_delay: Optional[float] = None) -> float:
        """Wait if necessary to comply with domain rate limits and backoff periods.
        
        Returns:
            The number of seconds slept (0.0 if no wait was needed).
        """
        domain = self._extract_domain(url)
        if not domain or domain == "unknown":
            return 0.0

        lock = await self._get_lock(domain)
        async with lock:
            now = time.time()
            slept = 0.0

            # 1. Check if domain is in 429 Retry-After backoff
            backoff_time = self._backoff_until.get(domain, 0.0)
            if backoff_time > now:
                wait_needed = backoff_time - now
                logger.info(f"Rate limiting active for {domain}: backing off for {wait_needed:.2f}s")
                await asyncio.sleep(wait_needed)
                slept += wait_needed
                now = time.time()

            # 2. Check standard inter-request delay
            min_delay = custom_delay if custom_delay is not None else self.default_min_delay
            last_time = self._last_access.get(domain, 0.0)
            elapsed = now - last_time

            if elapsed < min_delay:
                wait_needed = min_delay - elapsed
                await asyncio.sleep(wait_needed)
                slept += wait_needed

            self._last_access[domain] = time.time()
            return slept

    def register_429_backoff(self, url: str, retry_after_seconds: float) -> None:
        """Register a Retry-After backoff period for a domain."""
        domain = self._extract_domain(url)
        if not domain or domain == "unknown":
            return
        effective_delay = max(1.0, min(retry_after_seconds, 300.0))  # Cap at 5 mins
        self._backoff_until[domain] = time.time() + effective_delay
        logger.warning(f"Registered 429 rate limit backoff for {domain}: {effective_delay:.1f}s")

    def clear(self) -> None:
        """Reset rate limiter state (useful for tests)."""
        self._last_access.clear()
        self._backoff_until.clear()
        self._locks.clear()


# Global singleton instance
domain_rate_limiter = DomainRateLimiter(default_min_delay_seconds=0.5)
