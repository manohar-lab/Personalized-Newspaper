"""models.py — Phase 5 Extraction Data Models and Enums.

Defines the core statuses, methods, and data structures for article extraction.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
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


class ExtractionMethod(str, Enum):
    TRAFILATURA = "TRAFILATURA"
    JSON_LD = "JSON_LD"
    OPENGRAPH = "OPENGRAPH"
    FALLBACK = "FALLBACK"


class RobotsAccess(str, Enum):
    ALLOWED = "ALLOWED"
    DISALLOWED = "DISALLOWED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ExtractedMetadata:
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    publication_date: Optional[datetime] = None
    image_url: Optional[str] = None
    canonical_url: Optional[str] = None
    language: Optional[str] = None
    article_body: Optional[str] = None
    is_paywalled: bool = False
    paywall_indicator: Optional[str] = None


@dataclass
class ExtractedArticleData:
    url: str
    status: ExtractionStatus = ExtractionStatus.NOT_ATTEMPTED
    method: Optional[ExtractionMethod] = None
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    publication_date: Optional[datetime] = None
    image_url: Optional[str] = None
    canonical_url: Optional[str] = None
    language: str = "en"
    content_hash: Optional[str] = None
    content_length: int = 0
    reading_time_minutes: int = 1
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
    error: Optional[str] = None
