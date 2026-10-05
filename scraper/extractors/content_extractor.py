"""
content_extractor.py — Phase 5 Web Article Extraction

Extracts the main article body and metadata from raw HTML using multiple
strategies in priority order:

1. JSON-LD structured data (most reliable when present)
2. OpenGraph / Twitter Card meta tags
3. Readability-style heuristic extraction (pure-Python implementation)

Design principles:
- Never raises exceptions to the caller: returns ExtractedContent with
  `success=False` if extraction fails.
- Clean, sentence-safe text output (no broken mid-sentence truncation).
- All fields are optional; caller should validate before persisting.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from html.parser import HTMLParser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class ExtractedContent:
    """Represents content extracted from a web page."""

    success: bool = False
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    body_text: Optional[str] = None        # Plain text of the article body
    body_html: Optional[str] = None        # Cleaned HTML of the article body
    image_url: Optional[str] = None
    published_at_raw: Optional[str] = None  # Raw date string, caller normalises
    language: Optional[str] = None
    word_count: int = 0
    extraction_method: str = "none"         # json_ld | opengraph | readability | none
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript|nav|header|footer|aside|form)[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

# Tags whose content carries tracking / boilerplate
_JUNK_CLASS_RE = re.compile(
    r'(class|id)=["\'][^"\']*'
    r'(nav|menu|header|footer|sidebar|ad|advertisement|promo|social|share|'
    r'comment|related|subscribe|cookie|banner|popup|modal|widget)[^"\']*["\']',
    re.IGNORECASE,
)


def _strip_tags(html: str) -> str:
    """Strips all HTML tags and returns plain text."""
    no_tags = _HTML_TAG_RE.sub(" ", html)
    return _WHITESPACE_RE.sub(" ", no_tags).strip()


def _remove_boilerplate(html: str) -> str:
    """Removes obvious boilerplate sections before extraction."""
    cleaned = _SCRIPT_STYLE_RE.sub(" ", html)
    return cleaned


# ---------------------------------------------------------------------------
# Simple HTML meta/tag parser
# ---------------------------------------------------------------------------

class _MetaExtractor(HTMLParser):
    """
    SAX-style parser to extract:
    - <title>
    - <meta> og:*, twitter:*, name="author", name="description", etc.
    - JSON-LD <script type="application/ld+json">
    - <html lang="...">
    """

    def __init__(self):
        super().__init__()
        self.title: Optional[str] = None
        self.og_title: Optional[str] = None
        self.og_description: Optional[str] = None
        self.og_image: Optional[str] = None
        self.twitter_title: Optional[str] = None
        self.twitter_description: Optional[str] = None
        self.twitter_image: Optional[str] = None
        self.meta_description: Optional[str] = None
        self.meta_author: Optional[str] = None
        self.article_author: Optional[str] = None
        self.article_published: Optional[str] = None
        self.json_ld_blocks: list[str] = []
        self.language: Optional[str] = None

        self._in_title = False
        self._in_json_ld = False
        self._json_ld_buf: list[str] = []
        self._title_buf: list[str] = []
        self._head_done = False

    def handle_starttag(self, tag: str, attrs):
        if self._head_done:
            return
        attr_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower == "html":
            self.language = attr_dict.get("lang")

        elif tag_lower == "title":
            self._in_title = True
            self._title_buf = []

        elif tag_lower == "meta":
            prop = (attr_dict.get("property") or "").lower()
            name = (attr_dict.get("name") or "").lower()
            content = attr_dict.get("content", "")

            if prop == "og:title":
                self.og_title = content
            elif prop == "og:description":
                self.og_description = content
            elif prop == "og:image":
                self.og_image = content
            elif prop == "twitter:title":
                self.twitter_title = content
            elif prop == "twitter:description":
                self.twitter_description = content
            elif prop == "twitter:image":
                self.twitter_image = content
            elif name == "description":
                self.meta_description = content
            elif name == "author":
                self.meta_author = content
            elif prop == "article:author":
                self.article_author = content
            elif prop == "article:published_time":
                self.article_published = content

        elif tag_lower == "script":
            script_type = attr_dict.get("type", "")
            if "application/ld+json" in script_type:
                self._in_json_ld = True
                self._json_ld_buf = []

        elif tag_lower == "body":
            self._head_done = True

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._in_title = False
            self.title = "".join(self._title_buf).strip() or None
        elif tag_lower == "script" and self._in_json_ld:
            self._in_json_ld = False
            block = "".join(self._json_ld_buf).strip()
            if block:
                self.json_ld_blocks.append(block)

    def handle_data(self, data: str):
        if self._in_title:
            self._title_buf.append(data)
        elif self._in_json_ld:
            self._json_ld_buf.append(data)


# ---------------------------------------------------------------------------
# JSON-LD extraction
# ---------------------------------------------------------------------------

def _extract_from_json_ld(blocks: list[str]) -> dict:
    """
    Extracts article metadata from JSON-LD blocks.
    Looks for @type in (Article, NewsArticle, BlogPosting).
    """
    article_types = {"Article", "NewsArticle", "BlogPosting", "ReportageNewsArticle"}

    for block in blocks:
        try:
            data = json.loads(block)
            # Handle @graph arrays
            candidates = []
            if isinstance(data, list):
                candidates = data
            elif isinstance(data, dict):
                graph = data.get("@graph")
                if isinstance(graph, list):
                    candidates = graph
                else:
                    candidates = [data]

            for item in candidates:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("@type", "")
                types = item_type if isinstance(item_type, list) else [item_type]
                if any(t in article_types for t in types):
                    result = {}

                    # Title
                    headline = item.get("headline") or item.get("name")
                    if headline and isinstance(headline, str):
                        result["title"] = headline.strip()

                    # Author
                    author_raw = item.get("author")
                    if isinstance(author_raw, dict):
                        result["author"] = author_raw.get("name")
                    elif isinstance(author_raw, list):
                        names = [
                            a.get("name") for a in author_raw
                            if isinstance(a, dict) and a.get("name")
                        ]
                        if names:
                            result["author"] = ", ".join(names)
                    elif isinstance(author_raw, str):
                        result["author"] = author_raw

                    # Description
                    desc = item.get("description") or item.get("abstract")
                    if isinstance(desc, str):
                        result["description"] = desc.strip()

                    # Image
                    img = item.get("image")
                    if isinstance(img, str):
                        result["image_url"] = img
                    elif isinstance(img, dict):
                        result["image_url"] = img.get("url")
                    elif isinstance(img, list) and img:
                        first = img[0]
                        result["image_url"] = first if isinstance(first, str) else (
                            first.get("url") if isinstance(first, dict) else None
                        )

                    # Published date
                    pub = item.get("datePublished") or item.get("dateCreated")
                    if pub and isinstance(pub, str):
                        result["published_at_raw"] = pub

                    if result:
                        return result
        except Exception:
            continue

    return {}


# ---------------------------------------------------------------------------
# Readability-style body extraction (lightweight heuristic)
# ---------------------------------------------------------------------------

# Candidate tag patterns for article body content
_CONTENT_TAGS = re.compile(
    r"<(article|main|div|section)[^>]*>",
    re.IGNORECASE,
)

# Positive signals in class/id names → likely article body
_POSITIVE_RE = re.compile(
    r'(?:class|id)=["\'][^"\']*'
    r'(?:article|post|content|story|body|text|entry|main|prose|'
    r'article-body|post-body|story-body|article__body|article-content)[^"\']*["\']',
    re.IGNORECASE,
)

# Negative signals → boilerplate
_NEGATIVE_RE = re.compile(
    r'(?:class|id)=["\'][^"\']*'
    r'(?:nav|menu|sidebar|header|footer|comment|related|subscribe|'
    r'ad|advertisement|promo|social|share|widget|popup|modal|cookie|'
    r'newsletter|recommended|trending|most-read)[^"\']*["\']',
    re.IGNORECASE,
)


def _score_block(html_block: str) -> int:
    """Simple scoring heuristic for a candidate HTML block."""
    score = 0
    if _POSITIVE_RE.search(html_block):
        score += 25
    if _NEGATIVE_RE.search(html_block):
        score -= 25
    # Length of stripped text as a proxy for content density
    text = _strip_tags(html_block)
    word_count = len(text.split())
    score += min(word_count, 200)  # Cap contribution
    # Paragraph count
    para_count = len(re.findall(r"<p[^>]*>", html_block, re.IGNORECASE))
    score += para_count * 3
    return score


def _extract_body_heuristic(html: str) -> Optional[str]:
    """
    Finds the best candidate block for article body content.
    Returns plain text of the best block, or None if nothing useful found.
    """
    # First, remove obvious boilerplate sections
    cleaned = _remove_boilerplate(html)

    # Find all top-level candidate blocks
    # We split on open tags and find matching content
    candidates: list[tuple[int, str]] = []

    # Look for <article> first — highest confidence
    article_matches = list(re.finditer(r"<article[^>]*>(.*?)</article>", cleaned, re.DOTALL | re.IGNORECASE))
    for m in article_matches:
        content = m.group(0)
        score = _score_block(content)
        candidates.append((score + 50, content))  # Bonus for article tag

    # Look for <main>
    main_matches = list(re.finditer(r"<main[^>]*>(.*?)</main>", cleaned, re.DOTALL | re.IGNORECASE))
    for m in main_matches:
        content = m.group(0)
        score = _score_block(content)
        candidates.append((score + 30, content))

    # Look for divs/sections with positive class signals
    div_matches = list(re.finditer(
        r'<(div|section)[^>]*(?:class|id)=["\'][^"\']*(?:article|post|content|story|body|prose|entry)[^"\']*["\'][^>]*>(.*?)</\1>',
        cleaned,
        re.DOTALL | re.IGNORECASE,
    ))
    for m in div_matches:
        content = m.group(0)
        score = _score_block(content)
        candidates.append((score, content))

    if not candidates:
        return None

    # Select best candidate
    best_score, best_block = max(candidates, key=lambda x: x[0])

    # Minimum quality gate: must have at least 50 words
    text = _strip_tags(best_block)
    words = text.split()
    if len(words) < 50:
        return None

    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ContentExtractor:
    """
    Extracts article content from raw HTML.

    Usage:
        extractor = ContentExtractor()
        result = extractor.extract(html, url)
    """

    def extract(self, html: str, url: str = "") -> ExtractedContent:
        """
        Extracts article content from raw HTML string.

        Never raises. Returns ExtractedContent with success=False on failure.
        """
        try:
            return self._do_extract(html, url)
        except Exception as exc:
            logger.warning(f"ContentExtractor failed for {url}: {exc}")
            return ExtractedContent(
                success=False,
                error=str(exc),
                extraction_method="none",
            )

    def _do_extract(self, html: str, url: str) -> ExtractedContent:
        result = ExtractedContent()

        # -- Step 1: Parse <head> metadata --
        parser = _MetaExtractor()
        try:
            parser.feed(html[:50000])  # Only parse first 50KB for head metadata
        except Exception:
            pass  # Partial parse is fine

        # -- Step 2: JSON-LD extraction --
        json_ld_data: dict = {}
        if parser.json_ld_blocks:
            json_ld_data = _extract_from_json_ld(parser.json_ld_blocks)

        # -- Step 3: Build metadata (priority: JSON-LD > OG/Twitter > <meta>) --
        # Title
        result.title = (
            json_ld_data.get("title")
            or parser.og_title
            or parser.twitter_title
            or parser.title
        )
        if result.title:
            result.title = _WHITESPACE_RE.sub(" ", result.title).strip()

        # Author
        result.author = (
            json_ld_data.get("author")
            or parser.article_author
            or parser.meta_author
        )

        # Description
        result.description = (
            json_ld_data.get("description")
            or parser.og_description
            or parser.twitter_description
            or parser.meta_description
        )
        if result.description:
            result.description = _strip_tags(result.description)
            result.description = _WHITESPACE_RE.sub(" ", result.description).strip()

        # Image
        result.image_url = (
            json_ld_data.get("image_url")
            or parser.og_image
            or parser.twitter_image
        )

        # Published date
        result.published_at_raw = (
            json_ld_data.get("published_at_raw")
            or parser.article_published
        )

        # Language
        result.language = parser.language

        # Set extraction method for metadata
        if json_ld_data:
            result.extraction_method = "json_ld"
        elif parser.og_title or parser.og_description:
            result.extraction_method = "opengraph"
        else:
            result.extraction_method = "none"

        # -- Step 4: Article body extraction --
        body_text = _extract_body_heuristic(html)
        if body_text:
            result.body_text = body_text
            result.word_count = len(body_text.split())
            # Only upgrade extraction_method to readability if body found
            if result.extraction_method == "none":
                result.extraction_method = "readability"
            else:
                result.extraction_method = result.extraction_method + "+readability"

        # -- Step 5: Success gate --
        # We consider it a success if we have at least a title or description
        if result.title or result.description or result.body_text:
            result.success = True
        else:
            result.error = "No extractable content found in page"
            result.extraction_method = "none"

        return result
