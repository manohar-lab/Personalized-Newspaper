"""fetcher.py — Phase 5 SSRF-Safe Web Page Fetcher.

Responsible for safely making HTTP GET requests to retrieve article HTML.
Enforces SSRF prevention, timeouts, redirect limits, and content size bounds.
"""
import ipaddress
import logging
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class FetchError(Exception):
    """Base exception for web fetching errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class SSRFValidationError(FetchError):
    """Raised when a URL fails SSRF safety validation."""
    pass


class WebPageFetcher:
    """SSRF-Safe Async Web Page Fetcher."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        max_content_size: Optional[int] = None,
        max_redirects: Optional[int] = None,
    ):
        self.user_agent = user_agent or settings.USER_AGENT
        self.timeout_seconds = timeout_seconds or settings.REQUEST_TIMEOUT
        self.max_content_size = max_content_size or settings.MAX_CONTENT_SIZE
        self.max_redirects = max_redirects or settings.MAX_REDIRECTS

    @staticmethod
    def is_ssrf_safe_url(url: str) -> Tuple[bool, str]:
        """Validate URL to ensure it is HTTP/HTTPS and does not target internal/private resources.
        
        Returns:
            (is_safe, error_reason)
        """
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

        # 2. Reject obvious internal/local hostnames
        if hostname_lower in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False, f"Forbidden host: '{hostname}' is a loopback address"

        if hostname_lower.endswith((".local", ".internal", ".localhost", ".lan", ".home")):
            return False, f"Forbidden internal domain suffix: '{hostname}'"

        # 3. Check direct IP address literals
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                return False, f"Forbidden IP address: '{ip}' is private or reserved"
        except ValueError:
            # Not an IP literal, it's a domain name. Resolve hostname to verify IP.
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                for item in addr_info:
                    sockaddr = item[4]
                    resolved_ip_str = sockaddr[0]
                    resolved_ip = ipaddress.ip_address(resolved_ip_str)
                    # Allow RFC 6052 NAT64 prefixes (64:ff9b::/96) if embedded IPv4 is not private
                    is_nat64 = isinstance(resolved_ip, ipaddress.IPv6Address) and resolved_ip in ipaddress.IPv6Network("64:ff9b::/96")
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
                # DNS resolution failure will be handled by fetch request
                pass
            except Exception as e:
                logger.debug(f"IP resolution check note for {hostname}: {e}")

        return True, ""

    async def fetch(self, url: str) -> Tuple[str, str, int]:
        """Fetch the HTML content of a webpage safely.
        
        Returns:
            (html_content, final_url, status_code)
            
        Raises:
            SSRFValidationError: if URL targets private/local networks
            FetchError: on HTTP errors, timeouts, oversized payloads
        """
        is_safe, reason = self.is_ssrf_safe_url(url)
        if not is_safe:
            raise SSRFValidationError(f"SSRF validation failed: {reason}")

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }

        transport = httpx.AsyncHTTPTransport(retries=1)
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=True,
            max_redirects=self.max_redirects,
            timeout=httpx.Timeout(self.timeout_seconds, connect=10.0),
            headers=headers,
        ) as client:
            try:
                response = await client.get(url)
            except httpx.TimeoutException as exc:
                raise FetchError(f"Request timed out after {self.timeout_seconds}s: {exc}")
            except httpx.TooManyRedirects as exc:
                raise FetchError(f"Exceeded maximum redirects ({self.max_redirects}): {exc}")
            except httpx.RequestError as exc:
                raise FetchError(f"Network request failed: {exc}")

            final_url = str(response.url)
            # Re-check final URL after redirects for SSRF
            is_final_safe, final_reason = self.is_ssrf_safe_url(final_url)
            if not is_final_safe:
                raise SSRFValidationError(f"Redirected to forbidden location: {final_reason}")

            if response.status_code == 403:
                raise FetchError("Access denied (HTTP 403)", status_code=403)
            elif response.status_code == 404:
                raise FetchError("Article not found (HTTP 404)", status_code=404)
            elif response.status_code >= 400:
                raise FetchError(f"HTTP error {response.status_code}", status_code=response.status_code)

            content_type = response.headers.get("content-type", "").lower()
            if content_type and not any(ct in content_type for ct in ("text/html", "application/xhtml+xml", "text/plain", "application/xml")):
                raise FetchError(f"Unsupported content-type: {content_type}")

            # Check content length
            raw_bytes = response.content
            if len(raw_bytes) > self.max_content_size:
                raise FetchError(f"Content size {len(raw_bytes)} bytes exceeds limit of {self.max_content_size} bytes")

            html_text = response.text
            return html_text, final_url, response.status_code
