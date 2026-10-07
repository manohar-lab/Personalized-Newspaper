"""validator.py — Phase 20 Content Validation, Paywall & Consent Page Detection.

Validates extracted article data, detecting paywalls, authentication blocks,
cookie consent walls, javascript requirements, CAPTCHAs, error pages, and low quality extraction.
"""
import re
from typing import Optional, Tuple

from app.core.config import settings
from app.extraction.models import ExtractedArticleData, ExtractionStatus
from app.extraction.quality import ArticleQualityScorer


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
        r"(?i)\bmetered article limit\b",
        r"(?i)\bbecome a subscriber to read\b",
    ]

    # Cookie / Consent notice patterns
    COOKIE_PATTERNS = [
        r"(?i)\baccept all cookies\b",
        r"(?i)\bwe value your privacy\b",
        r"(?i)\bmanage cookie preferences\b",
        r"(?i)\bthis website uses cookies to enhance\b",
        r"(?i)\bconsent to our use of cookies\b",
        r"(?i)\bgdpr consent notice\b",
        r"(?i)\bcookie policy and terms\b",
    ]

    # CAPTCHA / Bot detection patterns
    CHALLENGE_PATTERNS = [
        r"(?i)\bverify you are human\b",
        r"(?i)\battention required! \| cloudflare\b",
        r"(?i)\bchecking your browser before accessing\b",
        r"(?i)\bcaptcha\b",
        r"(?i)\bjust a moment\.\.\.\b",
        r"(?i)\bsecurity check to access\b",
    ]

    # JavaScript required patterns
    JS_PATTERNS = [
        r"(?i)\bplease enable javascript to view\b",
        r"(?i)\bjavascript is disabled\b",
        r"(?i)\byou need to enable javascript to run this app\b",
        r"(?i)\bthis site requires javascript\b",
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
        title = (article.title or article.headline or "").strip()
        if not title:
            return False, ExtractionStatus.FAILED, "Article title is missing or empty"

        # Check if title itself is a challenge, js requirement, or error
        if any(re.search(pat, title) for pat in self.CHALLENGE_PATTERNS):
            return False, ExtractionStatus.UNSUPPORTED, "Page is a bot challenge / CAPTCHA"
        if any(re.search(pat, title) for pat in self.JS_PATTERNS):
            return False, ExtractionStatus.JS_REQUIRED, "Page requires JavaScript execution"
        if any(re.search(pat, title) for pat in self.ERROR_PATTERNS):
            return False, ExtractionStatus.FAILED, "Page is an error page"

        # 2. Check body content
        content = (article.content or "").strip()

        # Check for JavaScript required pages
        for pat in self.JS_PATTERNS:
            if re.search(pat, content):
                return False, ExtractionStatus.JS_REQUIRED, "Page requires JavaScript to render article body"

        # Check for cookie consent pages
        cookie_matches = sum(1 for pat in self.COOKIE_PATTERNS if re.search(pat, content))
        if cookie_matches >= 2 or (cookie_matches >= 1 and len(content) < 300):
            return False, ExtractionStatus.COOKIE_CONSENT_PAGE, "Page is dominated by a cookie/privacy consent banner"

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

        if char_count < self.min_body_length or word_count < 25:
            return (
                False,
                ExtractionStatus.FAILED,
                f"Article body too short ({char_count} chars, {word_count} words; min {self.min_body_length} chars)",
            )

        # 4. Check for high density of navigation / boilerplate lines
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        if lines:
            short_lines = [line for line in lines if len(line.split()) <= 4]
            if len(short_lines) / len(lines) > 0.75 and len(lines) > 5:
                return False, ExtractionStatus.FAILED, "Content appears to be navigation/link list rather than article text"

        # 5. Evaluate quality score breakdown
        breakdown = ArticleQualityScorer.evaluate(article)
        article.quality_breakdown = breakdown
        article.quality_score = breakdown.overall_score

        if not breakdown.is_acceptable:
            return False, ExtractionStatus.LOW_QUALITY, f"Extraction quality score {breakdown.overall_score} below acceptable threshold"

        return True, ExtractionStatus.SUCCESS, "Valid article content"
