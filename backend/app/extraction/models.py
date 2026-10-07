"""models.py — Phase 20 Extraction Data Models and Enums.

Defines core statuses, methods, quality breakdowns, and data structures for article extraction.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import uuid


class ExtractionStatus(str, Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    ROBOTS_BLOCKED = "ROBOTS_BLOCKED"
    PAYWALL = "PAYWALL"
    ACCESS_DENIED = "ACCESS_DENIED"
    UNSUPPORTED = "UNSUPPORTED"
    COOKIE_CONSENT_PAGE = "COOKIE_CONSENT_PAGE"
    JS_REQUIRED = "JS_REQUIRED"
    LOW_QUALITY = "LOW_QUALITY"


class ExtractionMethod(str, Enum):
    TRAFILATURA = "TRAFILATURA"
    JSON_LD = "JSON_LD"
    OPENGRAPH = "OPENGRAPH"
    SOURCE_SPECIFIC = "SOURCE_SPECIFIC"
    FALLBACK = "FALLBACK"


class RobotsAccess(str, Enum):
    ALLOWED = "ALLOWED"
    DISALLOWED = "DISALLOWED"
    UNKNOWN = "UNKNOWN"


@dataclass
class FetchResponse:
    html: str = ""
    final_url: str = ""
    status_code: int = 200
    is_not_modified: bool = False
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_type: str = ""
    response_size_bytes: int = 0
    duration_ms: float = 0.0


@dataclass
class ExtractionQualityBreakdown:
    content_length_score: float = 0.0
    headline_score: float = 0.0
    metadata_score: float = 0.0
    date_score: float = 0.0
    author_score: float = 0.0
    structure_score: float = 0.0
    overall_score: float = 0.0
    is_acceptable: bool = True
    flags: List[str] = field(default_factory=list)


@dataclass
class ExtractedMetadata:
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    publication_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None
    image_url: Optional[str] = None
    canonical_url: Optional[str] = None
    language: Optional[str] = None
    article_body: Optional[str] = None
    is_paywalled: bool = False
    paywall_indicator: Optional[str] = None
    is_cookie_page: bool = False
    is_js_required: bool = False


@dataclass
class ExtractedArticleData:
    url: str
    status: ExtractionStatus = ExtractionStatus.NOT_ATTEMPTED
    method: Optional[ExtractionMethod] = None
    title: Optional[str] = None
    headline: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    publication_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None
    image_url: Optional[str] = None
    canonical_url: Optional[str] = None
    language: str = "en"
    content_hash: Optional[str] = None
    last_content_hash: Optional[str] = None
    content_length: int = 0
    reading_time_minutes: int = 1
    quality_score: float = 0.0
    quality_breakdown: Optional[ExtractionQualityBreakdown] = None
    extracted_at: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class ExtractionResult:
    article_id: uuid.UUID
    status: ExtractionStatus
    title: Optional[str] = None
    author: Optional[str] = None
    content_length: int = 0
    canonical_url: Optional[str] = None
    extraction_method: Optional[str] = None
    is_full_text_available: bool = False
    quality_score: float = 0.0
    error: Optional[str] = None
