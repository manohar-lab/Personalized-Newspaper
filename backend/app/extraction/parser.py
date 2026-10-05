"""parser.py — Phase 5 HTML & Structured Metadata Parser.

Extracts OpenGraph, Twitter Cards, Schema.org / JSON-LD, canonical URLs,
and paywall metadata from HTML documents.
"""
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from app.extraction.models import ExtractedMetadata

logger = logging.getLogger(__name__)


class HTMLMetadataParser:
    """Parses structured metadata (JSON-LD, OpenGraph, Twitter, standard meta) from HTML."""

    @staticmethod
    def parse(html: str, target_url: str = "") -> ExtractedMetadata:
        """Extract metadata from HTML markup."""
        if not html:
            return ExtractedMetadata()

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.debug(f"BeautifulSoup parsing failed: {e}")
            return ExtractedMetadata()

        metadata = ExtractedMetadata()

        # 1. Parse JSON-LD (Schema.org)
        json_ld_data = HTMLMetadataParser._parse_json_ld(soup)
        if json_ld_data:
            metadata.title = json_ld_data.get("headline") or json_ld_data.get("name")
            metadata.author = json_ld_data.get("author")
            metadata.description = json_ld_data.get("description")
            metadata.image_url = json_ld_data.get("image")
            metadata.canonical_url = json_ld_data.get("url") or json_ld_data.get("mainEntityOfPage")
            metadata.article_body = json_ld_data.get("articleBody")
            metadata.publication_date = json_ld_data.get("datePublished")
            if json_ld_data.get("isAccessibleForFree") is False:
                metadata.is_paywalled = True
                metadata.paywall_indicator = "JSON-LD: isAccessibleForFree=false"

        # 2. Parse OpenGraph & Twitter tags
        og_data = HTMLMetadataParser._parse_meta_tags(soup)

        # Merge with priority: JSON-LD > OpenGraph > standard meta
        if not metadata.title:
            metadata.title = og_data.get("og:title") or og_data.get("twitter:title") or og_data.get("meta:title")
        if not metadata.description:
            metadata.description = og_data.get("og:description") or og_data.get("twitter:description") or og_data.get("meta:description")
        if not metadata.author:
            metadata.author = og_data.get("meta:author") or og_data.get("article:author")
        if not metadata.image_url:
            metadata.image_url = og_data.get("og:image") or og_data.get("twitter:image")
        if not metadata.canonical_url:
            metadata.canonical_url = og_data.get("canonical") or og_data.get("og:url")

        # Check HTML title tag fallback
        if not metadata.title and soup.title and soup.title.string:
            title_text = soup.title.string.strip()
            # Clean common title suffixes like " - The New York Times"
            metadata.title = re.sub(r"\s*[|\-–—]\s*[^|\-–—]+$", "", title_text).strip() or title_text

        # Check date from meta tags if not found in JSON-LD
        if not metadata.publication_date:
            date_str = (
                og_data.get("article:published_time")
                or og_data.get("pubdate")
                or og_data.get("date")
                or og_data.get("meta:date")
            )
            if date_str:
                metadata.publication_date = HTMLMetadataParser._parse_date(date_str)

        # Language
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):  # type: ignore[union-attr]
            metadata.language = str(html_tag.get("lang"))[:10]  # type: ignore[union-attr]

        # Check paywall classes/markers
        if not metadata.is_paywalled:
            paywall_el = soup.find(class_=re.compile(r"paywall|subscriber-only|locked-content|restricted-article", re.I))
            if paywall_el:
                metadata.is_paywalled = True
                metadata.paywall_indicator = f"HTML class: {paywall_el.get('class')}"

        return metadata

    @staticmethod
    def _parse_json_ld(soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract and normalize Schema.org NewsArticle/Article data from <script type="application/ld+json">."""
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string.strip())
            except Exception:
                continue

            # Handle @graph wrapper
            items = []
            if isinstance(data, dict):
                if "@graph" in data and isinstance(data["@graph"], list):
                    items = data["@graph"]
                else:
                    items = [data]
            elif isinstance(data, list):
                items = data

            for item in items:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("@type", "")
                if isinstance(item_type, list):
                    item_type = " ".join(item_type)

                if any(t in str(item_type) for t in ("NewsArticle", "Article", "BlogPosting", "Report", "TechArticle")):
                    return HTMLMetadataParser._normalize_json_ld_article(item)

        return {}

    @staticmethod
    def _normalize_json_ld_article(item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize JSON-LD fields into standard dictionary."""
        result: Dict[str, Any] = {}
        
        # Headline / Title
        result["headline"] = item.get("headline") or item.get("name")

        # Author
        author = item.get("author")
        if isinstance(author, dict):
            result["author"] = author.get("name")
        elif isinstance(author, list) and author:
            names = [a.get("name") for a in author if isinstance(a, dict) and a.get("name")]
            result["author"] = ", ".join(names) if names else None
        elif isinstance(author, str):
            result["author"] = author

        # Description
        result["description"] = item.get("description")

        # Article body
        result["articleBody"] = item.get("articleBody")

        # Date Published
        date_str = item.get("datePublished") or item.get("dateCreated")
        if date_str:
            result["datePublished"] = HTMLMetadataParser._parse_date(date_str)

        # Image
        image = item.get("image")
        if isinstance(image, dict):
            result["image"] = image.get("url")
        elif isinstance(image, list) and image:
            first = image[0]
            result["image"] = first.get("url") if isinstance(first, dict) else str(first)
        elif isinstance(image, str):
            result["image"] = image

        # URL / Canonical
        url = item.get("url") or item.get("mainEntityOfPage")
        if isinstance(url, dict):
            result["url"] = url.get("@id") or url.get("url")
        elif isinstance(url, str):
            result["url"] = url

        # Paywall flag
        if "isAccessibleForFree" in item:
            result["isAccessibleForFree"] = bool(item["isAccessibleForFree"])

        return result

    @staticmethod
    def _parse_meta_tags(soup: BeautifulSoup) -> Dict[str, str]:
        """Extract OpenGraph, Twitter, and standard meta tags."""
        data: Dict[str, str] = {}

        # Canonical link
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):  # type: ignore[union-attr]
            data["canonical"] = str(canonical.get("href")).strip()  # type: ignore[union-attr]

        # Meta tags
        for meta in soup.find_all("meta"):
            prop = meta.get("property") or meta.get("name")
            content = meta.get("content")
            if not prop or not content:
                continue
            prop_str = str(prop).lower().strip()
            content_str = str(content).strip()

            if prop_str in ("og:title", "twitter:title"):
                data[prop_str] = content_str
            elif prop_str in ("og:description", "twitter:description", "description"):
                data[prop_str] = content_str
                if prop_str == "description":
                    data["meta:description"] = content_str
            elif prop_str in ("og:image", "twitter:image", "twitter:image:src"):
                data["og:image" if "og:" in prop_str else "twitter:image"] = content_str
            elif prop_str in ("og:url", "twitter:url"):
                data["og:url"] = content_str
            elif prop_str in ("author", "article:author", "dc.creator"):
                data["meta:author"] = content_str
            elif prop_str in ("article:published_time", "pubdate", "date", "dc.date"):
                data[prop_str] = content_str

        return data

    @staticmethod
    def _parse_date(date_str: Any) -> Optional[datetime]:
        """Safely parse a date string into a datetime object."""
        if not date_str or not isinstance(date_str, str):
            return None
        try:
            return dateutil_parser.parse(date_str)
        except Exception:
            return None
