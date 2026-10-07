"""fetcher.py — Phase 20 SSRF-Safe, Rate-Limited Web Page Fetcher with Conditional Requests.

Responsible for safely making HTTP GET requests to retrieve article and feed HTML/XML.
Enforces SSRF prevention, timeouts, redirect limits, content size bounds,
per-domain rate limiting, conditional caching (ETag / Last-Modified), and exponential backoff retry.
"""
import asyncio
import ipaddress
import logging
import random
import socket
import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.extraction.models import FetchResponse
from app.extraction.rate_limiter import domain_rate_limiter

logger = logging.getLogger(__name__)

TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
PERMANENT_FAIL_CODES = {400, 401, 403, 404, 410, 451}


class FetchError(Exception):
    """Base exception for web fetching errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class SSRFValidationError(FetchError):
    """Raised when a URL fails SSRF safety validation."""
    pass


class WebPageFetcher:
    """SSRF-Safe Async Web Page & Feed Fetcher."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        max_content_size: Optional[int] = None,
        max_redirects: Optional[int] = None,
        max_retries: int = 2,
    ):
        self.user_agent = user_agent or settings.USER_AGENT
        self.timeout_seconds = timeout_seconds or settings.REQUEST_TIMEOUT
        self.max_content_size = max_content_size or settings.MAX_CONTENT_SIZE
        self.max_redirects = max_redirects or settings.MAX_REDIRECTS
        self.max_retries = max_retries

    @staticmethod
    def is_ssrf_safe_url(url: str) -> Tuple[bool, str]:
        """Validate URL to ensure it is HTTP/HTTPS and does not target internal/private resources."""
        if not url or not isinstance(url, str):
            return False, "URL is empty or not a string"

        try:
            parsed = urlparse(url.strip())
        except Exception as e:
            return False, f"Malformed URL: {e}"

        # 1. Scheme check: only http and https allowed
        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"Invalid scheme: '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

        hostname = parsed.hostname
        if not hostname:
            return False, "URL has no hostname"

        hostname_lower = hostname.lower()

        # 2. Reject internal/local hostnames
        if hostname_lower in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254"):
            return False, f"Forbidden host: '{hostname}' is an internal/loopback/metadata address"

        if hostname_lower.endswith((".local", ".internal", ".localhost", ".lan", ".home")):
            return False, f"Forbidden internal domain suffix: '{hostname}'"

        # 3. Check direct IP address literals
        try:
            ip = ipaddress.ip_address(hostname)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return False, f"Forbidden IP address: '{ip}' is private or reserved"
        except ValueError:
            # Domain name -> resolve hostname to verify IP
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                for item in addr_info:
                    sockaddr = item[4]
                    resolved_ip_str = sockaddr[0]
                    resolved_ip = ipaddress.ip_address(resolved_ip_str)
                    is_nat64 = isinstance(
                        resolved_ip, ipaddress.IPv6Address
                    ) and resolved_ip in ipaddress.IPv6Network("64:ff9b::/96")
                    is_bad = (
                        resolved_ip.is_private
                        or resolved_ip.is_loopback
                        or resolved_ip.is_link_local
                        or (resolved_ip.is_reserved and not is_nat64)
                        or resolved_ip.is_multicast
                        or resolved_ip.is_unspecified
                    )
                    if is_bad:
                        return False, f"Resolved IP '{resolved_ip_str}' for host '{hostname}' is private/reserved"
            except socket.gaierror:
                pass
            except Exception as e:
                logger.debug(f"IP resolution check note for {hostname}: {e}")

        return True, ""

    async def fetch_safe(
        self,
        url: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> FetchResponse:
        """Fetch a webpage with SSRF checks, per-domain rate limiting, conditional headers, and retries.
        
        Returns:
            FetchResponse dataclass.
        """
        is_safe, reason = self.is_ssrf_safe_url(url)
        if not is_safe:
            raise SSRFValidationError(f"SSRF validation failed: {reason}")

        # Comply with rate limiting
        await domain_rate_limiter.acquire(url)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }
        if etag:
            headers["If-None-Match"] = etag.strip()
        if last_modified:
            headers["If-Modified-Since"] = last_modified.strip()
        if custom_headers:
            headers.update(custom_headers)

        transport = httpx.AsyncHTTPTransport(retries=0)
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    transport=transport,
                    follow_redirects=True,
                    max_redirects=self.max_redirects,
                    timeout=httpx.Timeout(self.timeout_seconds, connect=8.0),
                    headers=headers,
                ) as client:
                    response = await client.get(url)
                    duration_ms = (time.time() - start_time) * 1000

                    final_url = str(response.url)
                    # Re-verify final URL after redirects for SSRF safety
                    is_final_safe, final_reason = self.is_ssrf_safe_url(final_url)
                    if not is_final_safe:
                        raise SSRFValidationError(f"Redirected to forbidden location: {final_reason}")

                    # 1. Check for 304 Not Modified
                    if response.status_code == 304:
                        return FetchResponse(
                            html="",
                            final_url=final_url,
                            status_code=304,
                            is_not_modified=True,
                            etag=response.headers.get("etag") or etag,
                            last_modified=response.headers.get("last-modified") or last_modified,
                            duration_ms=duration_ms,
                        )

                    # 2. Check for 429 Too Many Requests (handle Retry-After)
                    if response.status_code == 429:
                        retry_after = response.headers.get("retry-after")
                        delay = 5.0
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = 5.0
                        domain_rate_limiter.register_429_backoff(url, delay)
                        if attempt < self.max_retries:
                            backoff = delay + random.uniform(0.1, 0.5)
                            logger.info(f"Received 429 for {url}, retrying in {backoff:.1f}s (attempt {attempt+1}/{self.max_retries})")
                            await asyncio.sleep(backoff)
                            continue
                        raise FetchError(f"Rate limited by server (HTTP 429)", status_code=429)

                    # 3. Check for transient errors
                    if response.status_code in TRANSIENT_STATUS_CODES:
                        if attempt < self.max_retries:
                            backoff = (2 ** attempt) + random.uniform(0.1, 0.6)
                            logger.info(f"Transient HTTP {response.status_code} for {url}, retrying in {backoff:.1f}s")
                            await asyncio.sleep(backoff)
                            continue
                        raise FetchError(f"HTTP error {response.status_code}", status_code=response.status_code)

                    # 4. Permanent error codes
                    if response.status_code in PERMANENT_FAIL_CODES:
                        raise FetchError(f"HTTP error {response.status_code}", status_code=response.status_code)

                    if response.status_code >= 400:
                        raise FetchError(f"HTTP error {response.status_code}", status_code=response.status_code)

                    content_type = response.headers.get("content-type", "").lower()
                    allowed_types = (
                        "text/html",
                        "application/xhtml+xml",
                        "text/plain",
                        "application/xml",
                        "text/xml",
                        "application/rss+xml",
                        "application/atom+xml",
                    )
                    if content_type and not any(ct in content_type for ct in allowed_types):
                        raise FetchError(f"Unsupported content-type: {content_type}", status_code=415)

                    raw_bytes = response.content
                    if len(raw_bytes) > self.max_content_size:
                        raise FetchError(
                            f"Content size {len(raw_bytes)} bytes exceeds limit of {self.max_content_size} bytes",
                            status_code=413,
                        )

                    return FetchResponse(
                        html=response.text,
                        final_url=final_url,
                        status_code=response.status_code,
                        is_not_modified=False,
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                        content_type=content_type,
                        response_size_bytes=len(raw_bytes),
                        duration_ms=duration_ms,
                    )

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                if attempt < self.max_retries:
                    backoff = (2 ** attempt) + random.uniform(0.1, 0.6)
                    logger.info(f"Network error {exc} on {url}, retrying in {backoff:.1f}s")
                    await asyncio.sleep(backoff)
                    continue
                raise FetchError(f"Network request failed after {self.max_retries} retries: {exc}")
            except (SSRFValidationError, FetchError):
                raise
            except httpx.TooManyRedirects as exc:
                raise FetchError(f"Exceeded maximum redirects ({self.max_redirects}): {exc}")
            except Exception as exc:
                raise FetchError(f"Unexpected fetch error: {exc}")

        raise FetchError("Failed to fetch webpage after retries")

    async def fetch(self, url: str) -> Tuple[str, str, int]:
        """Backward-compatible fetch method returning (html_content, final_url, status_code)."""
        res = await self.fetch_safe(url)
        return res.html, res.final_url, res.status_code
