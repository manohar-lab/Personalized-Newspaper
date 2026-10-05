"""
article_validator.py — Phase 5 Content Validation

Validates cleaned article content before it can be persisted as full-text.

Validation rules:
1. Title must be present.
2. Body text must meet a minimum word count (configurable, default 100).
3. Body text must not be predominantly boilerplate/navigation text.
4. Description must be present (can fall back from body if missing).

A ValidationResult with `valid=False` does NOT fail the pipeline —
the article stays in the database with RSS metadata only and
`is_full_text_available=False`.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

# Minimum acceptable word count for full text
DEFAULT_MIN_WORD_COUNT = 100

# Patterns that suggest content is mostly boilerplate, not article body
_BOILERPLATE_PATTERNS = [
    re.compile(r"\bjavascript\s+required\b", re.IGNORECASE),
    re.compile(r"\benable\s+javascript\b", re.IGNORECASE),
    re.compile(r"\bplease\s+enable\s+cookies\b", re.IGNORECASE),
    re.compile(r"\baccess\s+denied\b", re.IGNORECASE),
    re.compile(r"\b403\s+forbidden\b", re.IGNORECASE),
    re.compile(r"\b404\s+not\s+found\b", re.IGNORECASE),
    re.compile(r"\bsubscribe\s+to\s+read\b", re.IGNORECASE),
    re.compile(r"\bcreate\s+a\s+free\s+account\b", re.IGNORECASE),
    re.compile(r"\bsign\s+in\s+to\s+read\b", re.IGNORECASE),
    re.compile(r"\bregister\s+to\s+continue\b", re.IGNORECASE),
    re.compile(r"\bpaywall\b", re.IGNORECASE),
]

# If these phrases appear near the start, it's often a gated-content page
_EARLY_PAYWALL_PATTERNS = [
    re.compile(r"\bpremium\s+content\b", re.IGNORECASE),
    re.compile(r"\bsubscribers?\s+only\b", re.IGNORECASE),
    re.compile(r"\bbecome\s+a\s+member\b", re.IGNORECASE),
]


@dataclass
class ValidationResult:
    """Represents the outcome of content validation."""

    valid: bool = False
    reasons: list[str] = field(default_factory=list)
    word_count: int = 0
    has_body: bool = False
    has_title: bool = False
    has_description: bool = False
    is_paywall_detected: bool = False


class ArticleValidator:
    """
    Validates cleaned article content before persisting as full text.

    Usage:
        validator = ArticleValidator(min_word_count=100)
        result = validator.validate(cleaned_content)
    """

    def __init__(self, min_word_count: int = DEFAULT_MIN_WORD_COUNT):
        self.min_word_count = min_word_count

    def validate(self, cleaned) -> ValidationResult:
        """
        Validates a CleanedContent instance.

        Args:
            cleaned: CleanedContent instance from ContentCleaner.

        Returns:
            ValidationResult explaining what passed/failed.
        """
        result = ValidationResult()
        reasons: list[str] = []

        # 1. Title check
        if cleaned.title and len(cleaned.title.strip()) >= 5:
            result.has_title = True
        else:
            reasons.append("missing_or_short_title")

        # 2. Description check
        if cleaned.description and len(cleaned.description.strip()) >= 20:
            result.has_description = True
        else:
            reasons.append("missing_or_short_description")

        # 3. Body text check
        body = cleaned.body_text or ""
        word_count = len(body.split()) if body else 0
        result.word_count = word_count

        if body and word_count >= self.min_word_count:
            result.has_body = True
        elif body and word_count > 0:
            reasons.append(f"body_too_short ({word_count} < {self.min_word_count} words)")
        else:
            reasons.append("no_body_text")

        # 4. Boilerplate / paywall detection
        # Check both body and description (short paywall pages may only have description)
        check_body = (body or "")[:2000]
        check_desc = (cleaned.description or "")[:500]
        check_text = check_body or check_desc  # Prefer body, fall back to description

        for pattern in _BOILERPLATE_PATTERNS:
            if pattern.search(check_text):
                reasons.append(f"boilerplate_detected: {pattern.pattern[:40]}")
                break  # One match is enough

        # Check early paywall signals in body OR description
        check_early = (body or cleaned.description or "")[:500]
        for pattern in _EARLY_PAYWALL_PATTERNS:
            if pattern.search(check_early):
                result.is_paywall_detected = True
                reasons.append("paywall_detected")
                break

        # Validation passes if we have a title AND (description OR body)
        # and no boilerplate detected
        boilerplate_detected = any("boilerplate" in r or "paywall" in r for r in reasons)
        if (
            result.has_title
            and (result.has_description or result.has_body)
            and not boilerplate_detected
        ):
            result.valid = True
        else:
            if not reasons:
                reasons.append("validation_failed")

        result.reasons = reasons
        return result
