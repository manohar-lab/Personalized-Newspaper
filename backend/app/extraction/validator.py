"""validator.py — Phase 5 Content Validation & Paywall Detection.

Validates extracted article data, detecting paywalls, authentication blocks,
CAPTCHAs, error pages, and insufficient body content.
"""
import re
from typing import Optional, Tuple

from app.core.config import settings
from app.extraction.models import ExtractedArticleData, ExtractionStatus


class ArticleContentValidator:
    """Validates extracted article content and detects access barriers."""

    # Paywall phrases that indicate content behind subscription
    PAYWALL_PATTERNS = [
        r"(?i)\bsubscribe to continue\b",
        r"(?i)\bsign in to read\b",
        r"(?i)\bsubscription required\b",
        r"(?i)\bto continue reading\b",
        r"(?i)\bunlock this article\b",
        r"(?i)\bthis premium article is available to subscribers\b",
        r"(?i)\balready a subscriber\? log in\b",
        r"(?i)\byou have reached your limit of free articles\b",
        r"(?i)\bmembers only\b",
        r"(?i)\bpaywall\b",
    ]

    # CAPTCHA / Bot detection patterns
    CHALLENGE_PATTERNS = [
        r"(?i)\bverify you are human\b",
        r"(?i)\battention required! \| cloudflare\b",
        r"(?i)\bchecking your browser before accessing\b",
        r"(?i)\bcaptcha\b",
        r"(?i)\bjust a moment\.\.\.\b",
        r"(?i)\bplease enable javascript to view this page\b",
        r"(?i)\bsecurity check to access\b",
    ]

    # Login / Auth patterns
    LOGIN_PATTERNS = [
        r"(?i)\bsign in to your account\b",
        r"(?i)\benter your password\b",
        r"(?i)\blog in to view this content\b",
        r"(?i)\bforgot password\b",
    ]

    # Error page patterns
    ERROR_PATTERNS = [
        r"(?i)\b404 not found\b",
        r"(?i)\bpage not found\b",
        r"(?i)\b500 internal server error\b",
        r"(?i)\baccess denied\b",
        r"(?i)\bthe page you requested could not be found\b",
    ]

    def __init__(self, min_body_length: Optional[int] = None):
        self.min_body_length = min_body_length or settings.MIN_ARTICLE_BODY_LENGTH

    def validate(self, article: ExtractedArticleData) -> Tuple[bool, ExtractionStatus, str]:
        """Validate extracted article data.
        
        Returns:
            (is_valid, ExtractionStatus, reason_message)
        """
        # 1. Check title
        if not article.title or not article.title.strip():
            return False, ExtractionStatus.FAILED, "Article title is missing or empty"

        # Check if title itself is a challenge or error
        title = article.title.strip()
        if any(re.search(pat, title) for pat in self.CHALLENGE_PATTERNS):
            return False, ExtractionStatus.UNSUPPORTED, "Page is a bot challenge / CAPTCHA"
        if any(re.search(pat, title) for pat in self.ERROR_PATTERNS):
            return False, ExtractionStatus.FAILED, "Page is an error page"

        # 2. Check body content
        content = (article.content or "").strip()

        # Check for paywall indicators in content or description
        full_text_to_check = f"{title} {article.description or ''} {content}"
        for pat in self.PAYWALL_PATTERNS:
            if re.search(pat, full_text_to_check):
                return False, ExtractionStatus.PAYWALL, f"Paywall detected: matches pattern '{pat}'"

        # Check for CAPTCHA / bot challenges
        for pat in self.CHALLENGE_PATTERNS:
            if re.search(pat, content):
                return False, ExtractionStatus.UNSUPPORTED, "Page requires JavaScript or is a bot challenge"

        # Check for login pages
        for pat in self.LOGIN_PATTERNS:
            if re.search(pat, content):
                return False, ExtractionStatus.ACCESS_DENIED, "Page requires authentication / login"

        # Check for error pages
        for pat in self.ERROR_PATTERNS:
            if re.search(pat, content):
                return False, ExtractionStatus.FAILED, "Page content indicates error page"

        # 3. Check content length
        char_count = len(content)
        word_count = len(content.split())

        if char_count < self.min_body_length or word_count < 30:
            return (
                False,
                ExtractionStatus.FAILED,
                f"Article body too short ({char_count} chars, {word_count} words; min {self.min_body_length} chars)",
            )

        # 4. Check for high density of navigation / boilerplate lines
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        if lines:
            short_lines = [line for line in lines if len(line.split()) <= 4]
            if len(short_lines) / len(lines) > 0.7 and len(lines) > 5:
                return False, ExtractionStatus.FAILED, "Content appears to be navigation/link list rather than article text"

        return True, ExtractionStatus.SUCCESS, "Valid article content"
