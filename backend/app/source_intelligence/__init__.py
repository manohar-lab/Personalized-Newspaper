"""__init__.py — Phase 15 Source Intelligence, Reliability & Quality Module."""
from app.source_intelligence.source_evaluator import SourceEvaluationService
from app.source_intelligence.quality_metrics import QualityMetricsCalculator
from app.source_intelligence.reliability import SourceReliabilityEngine
from app.source_intelligence.freshness import FreshnessCalculator
from app.source_intelligence.diversity import CoverageDiversityEngine
from app.source_intelligence.conflict_detector import ConflictDetector
from app.source_intelligence.models import (
    SourceHealthMetric,
    UserSourcePreference,
    UserSourceAffinity,
    SourceReport,
    ArticleReport,
)
from app.source_intelligence.schemas import (
    SourceItem,
    SourceDetail,
    SourceListResponse,
    SourceReportRequest,
    ArticleReportRequest,
    StoryCoverageResponse,
    ArticleCoverageItem,
    AdminSourceHealthResponse,
    ArticleQualityBreakdown,
)

__all__ = [
    "SourceEvaluationService",
    "QualityMetricsCalculator",
    "SourceReliabilityEngine",
    "FreshnessCalculator",
    "CoverageDiversityEngine",
    "ConflictDetector",
    "SourceHealthMetric",
    "UserSourcePreference",
    "UserSourceAffinity",
    "SourceReport",
    "ArticleReport",
    "SourceItem",
    "SourceDetail",
    "SourceListResponse",
    "SourceReportRequest",
    "ArticleReportRequest",
    "StoryCoverageResponse",
    "ArticleCoverageItem",
    "AdminSourceHealthResponse",
    "ArticleQualityBreakdown",
]
