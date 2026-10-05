"""
content_cleaner.py — Phase 5 Content Processing

Cleans and normalizes extracted article text for storage.

Responsibilities:
- Strip residual HTML tags from text.
- Normalize whitespace (collapse runs, trim).
- Remove non-printable / control characters.
- Truncate description and body to safe database lengths.
- Compute reading time estimate.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

# Maximum characters for the description field (matches Text column)
MAX_DESCRIPTION_CHARS = 1000
# Maximum characters for the full article body (Text column — very large but keep sane)
MAX_BODY_CHARS = 100_000

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTIPLE_NEWLINE_RE = re.compile(r"\n{3,}")
_MULTIPLE_SPACE_RE = re.compile(r"[ \t]{2,}")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _strip_html(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return _HTML_TAG_RE.sub(" ", text)


def _normalize_whitespace(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    # Collapse multiple spaces on the same line
    text = _MULTIPLE_SPACE_RE.sub(" ", text)
    # Collapse excessive newlines
    text = _MULTIPLE_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def _remove_control_chars(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    # Remove ASCII control characters (keep \n, \r, \t)
    text = _CONTROL_CHAR_RE.sub("", text)
    return text


def _truncate_at_word_boundary(text: str, max_chars: int) -> str:
    """Truncates text at max_chars without cutting mid-word."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Find last whitespace to avoid mid-word cut
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "…"


def _estimate_reading_time(text: Optional[str]) -> int:
    """Estimates reading time in minutes at 200 words per minute."""
    if not text:
        return 1
    word_count = len(text.split())
    minutes = max(1, round(word_count / 200))
    return minutes


@dataclass
class CleanedContent:
    """Cleaned, database-ready article content."""

    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    body_text: Optional[str] = None
    image_url: Optional[str] = None
    published_at_raw: Optional[str] = None
    language: Optional[str] = None
    word_count: int = 0
    reading_time_minutes: int = 1
    extraction_method: str = "none"


class ContentCleaner:
    """
    Cleans extracted article content for safe database storage.

    Usage:
        from scraper.extractors.content_extractor import ExtractedContent
        cleaner = ContentCleaner()
        cleaned = cleaner.clean(extracted)
    """

    def clean(self, extracted) -> CleanedContent:
        """
        Takes an ExtractedContent and returns CleanedContent ready for DB storage.

        Args:
            extracted: ExtractedContent instance from ContentExtractor.

        Returns:
            CleanedContent with sanitized fields.
        """
        # Clean title
        title = self._clean_field(extracted.title)

        # Clean author
        author = self._clean_field(extracted.author)
        if author and len(author) > 255:
            author = author[:255]

        # Clean description
        description = self._clean_field(extracted.description)
        if description and len(description) > MAX_DESCRIPTION_CHARS:
            description = _truncate_at_word_boundary(description, MAX_DESCRIPTION_CHARS)

        # Clean body text
        body_text = self._clean_field(extracted.body_text)
        if body_text and len(body_text) > MAX_BODY_CHARS:
            body_text = _truncate_at_word_boundary(body_text, MAX_BODY_CHARS)

        # Image URL — basic validation
        image_url = extracted.image_url
        if image_url and not image_url.startswith(("http://", "https://")):
            image_url = None

        # Language — keep short code only
        language = extracted.language
        if language and len(language) > 10:
            language = language[:10]

        # Word count
        word_count = len(body_text.split()) if body_text else 0
        if not word_count and description:
            word_count = len(description.split())

        reading_time = _estimate_reading_time(body_text or description)

        return CleanedContent(
            title=title,
            author=author,
            description=description,
            body_text=body_text,
            image_url=image_url,
            published_at_raw=extracted.published_at_raw,
            language=language,
            word_count=word_count,
            reading_time_minutes=reading_time,
            extraction_method=extracted.extraction_method,
        )

    @staticmethod
    def _clean_field(text: Optional[str]) -> Optional[str]:
        """
        Applies the full cleaning pipeline to a text field:
        strip HTML → remove control chars → normalize whitespace.
        """
        if not text:
            return None
        text = _strip_html(text)
        text = _remove_control_chars(text)
        text = _normalize_whitespace(text)
        return text if text else None
