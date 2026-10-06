"""schemas.py — Phase 15 Source Intelligence, Quality, Preferences & Coverage Schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ArticleQualityBreakdown(BaseModel):
    completeness_score: float = Field(..., description="Title, body length, author, description, image, etc. [0.0, 1.0]")
    metadata_score: float = Field(..., description="Date, canonical url, publisher info completeness [0.0, 1.0]")
    extraction_score: float = Field(..., description="COMPLETED vs PAYWALL vs PARTIAL [0.0, 1.0]")
    freshness_score: float = Field(..., description="Recency decay based on published_at [0.0, 1.0]")
    source_quality_contribution: float = Field(..., description="Weak Bayesian source prior [0.0, 1.0]")
    final_quality_score: float = Field(..., description="Aggregated article quality score [0.0, 1.0]")


class SourceItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    website_url: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool = True
    health_status: str = "HEALTHY"  # HEALTHY | DEGRADED | FAILING | INACTIVE
    freshness_score: float = 0.50
    quality_score: float = 0.50
    quality_confidence: float = 0.05
    reliability_score: float = 0.50
    coverage_score: float = 0.50
    extraction_success_rate: float = 1.0
    duplicate_rate: float = 0.0
    article_count: int = 0
    is_following: bool = False
    is_muted: bool = False
    last_evaluated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SourceDetail(SourceItem):
    recent_articles: List[Dict[str, Any]] = []
    topics_covered: List[str] = []
    latest_update: Optional[datetime] = None
    feed_count: int = 0
    daily_article_average: float = 0.0


class SourceListResponse(BaseModel):
    sources: List[SourceItem]
    total: int
    page: int = 1
    limit: int = 50


class SourceReportRequest(BaseModel):
    reason: str = Field(..., description="MISLEADING | LOW_QUALITY | BROKEN_ARTICLE | DUPLICATE | PAYWALL | OTHER")
    details: Optional[str] = Field(default=None, max_length=1000)


class ArticleReportRequest(BaseModel):
    reason: str = Field(..., description="MISLEADING | LOW_QUALITY | BROKEN_ARTICLE | DUPLICATE | PAYWALL | OTHER")
    details: Optional[str] = Field(default=None, max_length=1000)


class SourceHealthResponseItem(BaseModel):
    source_id: uuid.UUID
    source_name: str
    health_status: str
    fetch_count: int = 0
    fetch_success_count: int = 0
    fetch_success_rate: float = 1.0
    extraction_success_rate: float = 1.0
    duplicate_rate: float = 0.0
    consecutive_failures: int = 0
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    quality_score: float = 0.50
    quality_confidence: float = 0.05


class AdminSourceHealthResponse(BaseModel):
    total_sources: int
    healthy_count: int
    degraded_count: int
    failing_count: int
    inactive_count: int
    sources: List[SourceHealthResponseItem]


class ArticleCoverageItem(BaseModel):
    article_id: uuid.UUID
    title: str
    slug: str
    source_id: Optional[uuid.UUID] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None
    is_syndicated: bool = False
    is_primary: bool = False
    quality_score: float = 0.50
    summary: Optional[str] = None
    reading_time_minutes: int = 3
    extraction_status: str = "COMPLETED"


class StoryCoverageResponse(BaseModel):
    cluster_id: Optional[uuid.UUID] = None
    primary_article_id: uuid.UUID
    total_coverage_count: int
    independent_sources_count: int
    coverage_diversity_score: float = 0.0
    has_conflicts: bool = False
    conflict_summary: Optional[str] = None
    conflict_flag: Optional[str] = None  # None | POTENTIAL_CONFLICT
    variants: List[ArticleCoverageItem] = []
