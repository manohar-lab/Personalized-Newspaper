"""cleaner.py — Phase 5 Article Content Cleaning and Normalization.

Removes boilerplate, noise, residual markup, navigation blocks, and normalizes
whitespace and paragraph structures while preserving headings, lists, and quotes.
"""
import re
from typing import Optional
from bs4 import BeautifulSoup


class ContentCleaner:
    """Cleans and sanitizes raw extracted text and HTML into readable article content."""

    # Unwanted HTML elements to strip
    STRIP_TAGS = [
        "script", "style", "nav", "header", "footer", "aside",
        "noscript", "svg", "iframe", "form", "button", "input",
        "select", "textarea", "figure", "figcaption", "dialog"
    ]

    # Boilerplate patterns / phrases to remove or detect
    BOILERPLATE_PATTERNS = [
        r"(?i)share this story\s*(?:on facebook|on twitter|via email|copy link)?",
        r"(?i)sign up for our (?:daily|weekly)? newsletter",
        r"(?i)subscribe (?:now|today) for full access",
        r"(?i)follow us on (?:twitter|facebook|instagram|linkedin)",
        r"(?i)advertisement\b",
        r"(?i)sponsored content\b",
        r"(?i)read more:\s*.*$",
        r"(?i)related:\s*.*$",
        r"(?i)photo by:?\s*.*$",
        r"(?i)image credit:?\s*.*$",
        r"(?i)all rights reserved\.?",
        r"(?i)copyright \d{4}.*$",
        r"(?i)click here to (?:read|subscribe|join)",
    ]

    @classmethod
    def clean_html(cls, raw_html: str) -> str:
        """Strip non-content elements from raw HTML while preserving structure."""
        if not raw_html:
            return ""

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Decompose unwanted tags
        for tag_name in cls.STRIP_TAGS:
            for el in soup.find_all(tag_name):
                el.decompose()

        # 2. Decompose elements with ad/nav/cookie/social class or id
        noise_pattern = re.compile(
            r"cookie|banner|advertisement|sponsor|social-share|newsletter|sidebar|comments|breadcrumb|popup|modal",
            re.I
        )
        for el in soup.find_all(class_=noise_pattern):
            el.decompose()
        for el in soup.find_all(id=noise_pattern):
            el.decompose()

        # 3. Extract text paragraphs and headers
        blocks = []
        for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "li"]):
            text = el.get_text(strip=True)
            if not text:
                continue

            # Check if block is boilerplate
            if any(re.search(pat, text) for pat in cls.BOILERPLATE_PATTERNS):
                continue

            tag = el.name.lower()
            if tag.startswith("h"):
                blocks.append(f"\n### {text}\n")
            elif tag == "blockquote":
                blocks.append(f"\n> {text}\n")
            elif tag == "li":
                blocks.append(f"- {text}")
            else:
                blocks.append(f"\n{text}\n")

        cleaned_text = "\n".join(blocks)
        return cls.normalize_text(cleaned_text)

    @classmethod
    def normalize_text(cls, text: Optional[str]) -> str:
        """Normalize whitespace, collapse multiple blank lines, and format paragraphs."""
        if not text:
            return ""

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Remove control characters (except tab and newline)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        # Collapse excessive whitespace within lines (preserve indentation for lists if needed)
        lines = []
        for line in text.split("\n"):
            cleaned_line = " ".join(line.split())
            lines.append(cleaned_line)

        # Collapse more than 2 consecutive newlines into 2 (blank paragraph separator)
        combined = "\n".join(lines)
        combined = re.sub(r"\n{3,}", "\n\n", combined).strip()

        return combined

    @classmethod
    def clean_text_content(cls, raw_text: Optional[str]) -> str:
        """Clean plain text extracted from article extraction libraries."""
        if not raw_text:
            return ""

        # Remove common boilerplate lines
        lines = []
        for line in raw_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            # Skip single-line boilerplate
            if any(re.match(pat, stripped) for pat in cls.BOILERPLATE_PATTERNS):
                continue
            lines.append(stripped)

        cleaned = "\n\n".join(lines)
        return cls.normalize_text(cleaned)
