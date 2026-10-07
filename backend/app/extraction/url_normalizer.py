"""url_normalizer.py — Phase 20 URL Canonicalization & Normalization.

Normalizes article URLs, strips marketing/tracking parameters safely,
normalizes schemes/hostnames/ports/trailing slashes, and computes content fingerprints.
"""
import hashlib
import re
import urllib.parse
from typing import Optional, Set


TRACKING_PARAMS: Set[str] = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_reader",
    "fbclid",
    "gclid",
    "msclkid",
    "twclid",
    "igshid",
    "_ga",
    "_gl",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "ref_url",
    "ncid",
    "sr_share",
}


class URLNormalizer:
    """Utility for canonicalizing and normalizing URLs."""

    @staticmethod
    def normalize_url(raw_url: str) -> str:
        """Clean and normalize a URL safely.
        
        - Lowercases scheme and netloc.
        - Removes default ports (:80 on http, :443 on https).
        - Strips URL fragments (#section).
        - Strips common marketing/analytics tracking parameters.
        - Sorts remaining query parameters.
        - Trims redundant trailing slash if root path.
        """
        if not raw_url or not isinstance(raw_url, str):
            return ""

        url = raw_url.strip()
        try:
            parsed = urllib.parse.urlsplit(url)
        except Exception:
            return url

        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return url

        netloc = parsed.netloc.lower()

        # Remove default ports
        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]

        # Normalize path
        path = parsed.path or "/"
        # Collapse multiple slashes
        path = re.sub(r"/+", "/", path)
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        # Filter query params
        query = parsed.query
        if query:
            query_params = urllib.parse.parse_qsl(query, keep_blank_values=True)
            filtered_params = [
                (k, v) for k, v in query_params if k.lower() not in TRACKING_PARAMS
            ]
            filtered_params.sort(key=lambda x: x[0])
            new_query = urllib.parse.urlencode(filtered_params)
        else:
            new_query = ""

        # Reconstruct without fragment
        normalized = urllib.parse.urlunsplit((scheme, netloc, path, new_query, ""))
        return normalized

    @staticmethod
    def resolve_canonical(source_url: str, canonical_url: Optional[str]) -> str:
        """Determine canonical URL by validating and prioritizing <link rel="canonical">."""
        norm_source = URLNormalizer.normalize_url(source_url)
        if not canonical_url or not isinstance(canonical_url, str):
            return norm_source

        norm_canon = URLNormalizer.normalize_url(canonical_url)
        if not norm_canon:
            return norm_source

        # If canonical is relative, join with source
        if not norm_canon.startswith(("http://", "https://")):
            try:
                norm_canon = URLNormalizer.normalize_url(
                    urllib.parse.urljoin(source_url, canonical_url)
                )
            except Exception:
                return norm_source

        return norm_canon

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract clean domain name without www."""
        try:
            parsed = urllib.parse.urlsplit(url.strip())
            netloc = parsed.netloc.lower()
            if ":" in netloc:
                netloc = netloc.split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except Exception:
            return ""

    @staticmethod
    def normalize_title(title: str) -> str:
        """Normalize article title for comparison and duplicate detection."""
        if not title:
            return ""
        # Lowercase and replace non-alphanumeric chars with single space
        cleaned = re.sub(r"[^\w\s]", " ", title.lower())
        return " ".join(cleaned.split())

    @staticmethod
    def normalize_text_for_comparison(text: str) -> str:
        """Normalize text body for near-duplicate fingerprinting."""
        if not text:
            return ""
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        return " ".join(cleaned.split())

    @staticmethod
    def compute_article_fingerprint(
        canonical_url: str, title: str, content: Optional[str] = None
    ) -> str:
        """Generate SHA-256 fingerprint for article deduplication."""
        norm_title = URLNormalizer.normalize_title(title)
        norm_url = URLNormalizer.normalize_url(canonical_url)
        norm_body = URLNormalizer.normalize_text_for_comparison(content or "")[:1500]

        fingerprint_input = f"{norm_url}|||{norm_title}|||{norm_body}"
        return hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()
