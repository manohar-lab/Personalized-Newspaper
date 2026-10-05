import re
import html
import hashlib
import urllib.parse
from datetime import datetime, timezone, timedelta
import email.utils
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ncid",
    "_ga",
    "sr_share",
    "rss",
    "feed",
}

HTML_TAG_RE = re.compile(r"<[^>]+>")
IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")


class NormalizedArticle(BaseModel):
    title: str
    description: Optional[str] = None
    url: str
    canonical_url: Optional[str] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    published_at: datetime
    source_name: Optional[str] = None
    feed_name: Optional[str] = None
    language: str = "en"
    content_hash: str
    content: Optional[str] = None


class ArticleNormalizer:
    @staticmethod
    def normalize_url(url: Optional[str]) -> Optional[str]:
        if not url or not isinstance(url, str):
            return None
        url = url.strip()
        if not url:
            return None

        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return url

            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            if netloc.endswith(":80") and scheme == "http":
                netloc = netloc[:-3]
            elif netloc.endswith(":443") and scheme == "https":
                netloc = netloc[:-4]

            # Filter tracking query parameters
            query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            filtered_query_pairs = [
                (k, v) for k, v in query_pairs if k.lower() not in TRACKING_PARAMS
            ]
            normalized_query = urllib.parse.urlencode(filtered_query_pairs)

            # Clean path (strip trailing slash if path > 1 char)
            path = parsed.path
            if len(path) > 1 and path.endswith("/"):
                path = path[:-1]

            # Fragment is dropped for article canonical identification
            normalized = urllib.parse.urlunparse(
                (scheme, netloc, path, parsed.params, normalized_query, "")
            )
            return normalized
        except Exception:
            return url.strip()

    @staticmethod
    def clean_text(text: Optional[str]) -> Optional[str]:
        if not text or not isinstance(text, str):
            return None
        # Unescape HTML entities
        unescaped = html.unescape(text)
        # Strip HTML tags
        no_html = HTML_TAG_RE.sub(" ", unescaped)
        # Normalize whitespace
        cleaned = WHITESPACE_RE.sub(" ", no_html).strip()
        return cleaned if cleaned else None

    @staticmethod
    def normalize_date(
        date_raw: Any,
        fallback_time: Optional[datetime] = None,
    ) -> datetime:
        if fallback_time is None:
            fallback_time = datetime.now(timezone.utc)
        elif fallback_time.tzinfo is None:
            fallback_time = fallback_time.replace(tzinfo=timezone.utc)

        if not date_raw:
            return fallback_time

        # If it's a feedparser struct_time tuple
        if hasattr(date_raw, "tm_year"):
            try:
                dt = datetime(
                    date_raw.tm_year,
                    date_raw.tm_mon,
                    date_raw.tm_mday,
                    date_raw.tm_hour,
                    date_raw.tm_min,
                    date_raw.tm_sec,
                    tzinfo=timezone.utc,
                )
                return dt
            except Exception:
                pass

        # If it's already a datetime
        if isinstance(date_raw, datetime):
            if date_raw.tzinfo is None:
                return date_raw.replace(tzinfo=timezone.utc)
            return date_raw.astimezone(timezone.utc)

        # If it's a string
        if isinstance(date_raw, str):
            date_str = date_raw.strip()
            # Try RFC 2822 / 822 via email.utils
            try:
                parsed_email_dt = email.utils.parsedate_to_datetime(date_str)
                if parsed_email_dt:
                    if parsed_email_dt.tzinfo is None:
                        return parsed_email_dt.replace(tzinfo=timezone.utc)
                    return parsed_email_dt.astimezone(timezone.utc)
            except Exception:
                pass

            # Try ISO format
            try:
                iso_clean = date_str.replace("Z", "+00:00")
                parsed_iso = datetime.fromisoformat(iso_clean)
                if parsed_iso.tzinfo is None:
                    return parsed_iso.replace(tzinfo=timezone.utc)
                return parsed_iso.astimezone(timezone.utc)
            except Exception:
                pass

            # Try standard formats
            formats = [
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%a, %d %b %Y %H:%M:%S %Z",
                "%a, %d %b %Y %H:%M:%S %z",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    if dt.tzinfo is None:
                        return dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc)
                except Exception:
                    continue

        return fallback_time

    @staticmethod
    def compute_content_hash(
        title: str,
        url: str,
        description: Optional[str] = None,
    ) -> str:
        clean_title = (title or "").strip().lower()
        clean_url = (url or "").strip().lower()
        clean_desc = (description or "").strip().lower()[:100]
        seed = f"{clean_title}|{clean_url}|{clean_desc}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    @classmethod
    def extract_image_url(cls, entry: Any) -> Optional[str]:
        # 1. Media content (Yahoo Media RSS)
        media_content = getattr(entry, "media_content", None) or entry.get(
            "media_content", []
        )
        if isinstance(media_content, list):
            for m in media_content:
                if isinstance(m, dict) and "url" in m:
                    m_type = m.get("type", "")
                    m_medium = m.get("medium", "")
                    if m_type.startswith("image/") or m_medium == "image" or not m_type:
                        return m["url"]

        # 2. Media thumbnail
        media_thumbnail = getattr(entry, "media_thumbnail", None) or entry.get(
            "media_thumbnail", []
        )
        if isinstance(media_thumbnail, list):
            for t in media_thumbnail:
                if isinstance(t, dict) and "url" in t:
                    return t["url"]

        # 3. Enclosures
        enclosures = getattr(entry, "enclosures", None) or entry.get("enclosures", [])
        if isinstance(enclosures, list):
            for enc in enclosures:
                if isinstance(enc, dict) and "href" in enc:
                    enc_type = enc.get("type", "")
                    if enc_type.startswith("image/") or any(
                        enc["href"].lower().endswith(ext)
                        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]
                    ):
                        return enc["href"]

        # 4. Fallback: extract from summary or description HTML
        raw_summary = (
            getattr(entry, "summary", None)
            or entry.get("summary")
            or getattr(entry, "description", None)
            or entry.get("description")
            or ""
        )
        if isinstance(raw_summary, str):
            match = IMG_SRC_RE.search(raw_summary)
            if match:
                img_url = match.group(1).strip()
                if img_url.startswith("http://") or img_url.startswith("https://"):
                    return img_url

        return None

    @classmethod
    def extract_author(cls, entry: Any) -> Optional[str]:
        author_detail = getattr(entry, "author_detail", None) or entry.get(
            "author_detail"
        )
        if isinstance(author_detail, dict) and "name" in author_detail and author_detail["name"]:
            return cls.clean_text(author_detail["name"])

        authors = getattr(entry, "authors", None) or entry.get("authors")
        if isinstance(authors, list) and len(authors) > 0:
            first_auth = authors[0]
            if isinstance(first_auth, dict) and "name" in first_auth and first_auth["name"]:
                return cls.clean_text(first_auth["name"])

        author = getattr(entry, "author", None) or entry.get("author")
        if author and isinstance(author, str):
            # Clean email in parentheses if present, e.g. "Name (email@...)" -> "Name"
            cleaned_author = re.sub(r"\s*\([^)]*@[^)]*\)", "", author).strip()
            return cls.clean_text(cleaned_author or author)

        dc_creator = getattr(entry, "dc_creator", None) or entry.get("dc_creator")
        if dc_creator and isinstance(dc_creator, str):
            return cls.clean_text(dc_creator)

        return None

    @classmethod
    def extract_description(cls, entry: Any) -> Optional[str]:
        summary = (
            getattr(entry, "summary", None)
            or entry.get("summary")
            or getattr(entry, "description", None)
            or entry.get("description")
            or getattr(entry, "subtitle", None)
            or entry.get("subtitle")
        )
        return cls.clean_text(summary)

    @classmethod
    def normalize_entry(
        cls,
        entry: Any,
        source_name: Optional[str] = None,
        feed_name: Optional[str] = None,
        language: str = "en",
        retrieval_time: Optional[datetime] = None,
    ) -> Optional[NormalizedArticle]:
        # 1. Title
        raw_title = getattr(entry, "title", None) or entry.get("title")
        title = cls.clean_text(raw_title)
        if not title:
            return None

        # 2. URL
        raw_url = getattr(entry, "link", None) or entry.get("link")
        if not raw_url and hasattr(entry, "links"):
            links = entry.links
            if isinstance(links, list):
                for l in links:
                    if isinstance(l, dict) and l.get("rel") == "alternate" and "href" in l:
                        raw_url = l["href"]
                        break
                    elif isinstance(l, dict) and "href" in l:
                        raw_url = l["href"]

        if not raw_url or not isinstance(raw_url, str):
            return None

        normalized_url = cls.normalize_url(raw_url)
        if not normalized_url:
            return None

        # 3. Canonical URL
        canonical_url = normalized_url
        if hasattr(entry, "id") and entry.id and entry.id.startswith("http"):
            canonical_candidate = cls.normalize_url(entry.id)
            if canonical_candidate:
                canonical_url = canonical_candidate

        # 4. Description
        description = cls.extract_description(entry)

        # 5. Author
        author = cls.extract_author(entry)

        # 6. Image URL
        image_url = cls.extract_image_url(entry)

        # 7. Published Date
        date_raw = (
            getattr(entry, "published_parsed", None)
            or entry.get("published_parsed")
            or getattr(entry, "updated_parsed", None)
            or entry.get("updated_parsed")
            or getattr(entry, "published", None)
            or entry.get("published")
            or getattr(entry, "updated", None)
            or entry.get("updated")
            or getattr(entry, "created", None)
            or entry.get("created")
        )
        published_at = cls.normalize_date(date_raw, fallback_time=retrieval_time)

        # 8. Content Hash
        content_hash = cls.compute_content_hash(title, canonical_url, description)

        return NormalizedArticle(
            title=title,
            description=description,
            url=raw_url.strip(),
            canonical_url=canonical_url,
            author=author,
            image_url=image_url,
            published_at=published_at,
            source_name=source_name,
            feed_name=feed_name,
            language=language,
            content_hash=content_hash,
            content=None,
        )
