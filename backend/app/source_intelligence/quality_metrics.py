"""quality_metrics.py — Bayesian estimation, confidence calculation & article quality scoring."""
import math
from typing import Any, Dict, Optional, Tuple
from app.source_intelligence.schemas import ArticleQualityBreakdown


class QualityMetricsCalculator:
    """Calculates smoothed statistical quality metrics for sources and individual articles."""

    @staticmethod
    def bayesian_smoothed_rate(
        successes: float,
        total: float,
        prior_success: float = 8.0,
        prior_total: float = 10.0,
    ) -> float:
        """
        Calculates Laplace / Bayesian smoothed rate to prevent extreme 0% or 100% scores
        on small sample sizes.
        Default prior: 8 successes out of 10 trials (0.80 expectation).
        """
        if total < 0:
            total = 0
        if successes < 0:
            successes = 0
        if successes > total:
            successes = total

        numerator = successes + prior_success
        denominator = total + prior_total
        return round(numerator / denominator, 4)

    @staticmethod
    def compute_confidence(
        sample_count: int,
        target_scale: float = 40.0,
        min_confidence: float = 0.05,
        max_confidence: float = 0.95,
    ) -> float:
        """
        Computes statistical confidence score [0.05, 0.95] as sample count grows.
        New sources (0 articles) -> 0.05 confidence.
        Established sources (100+ articles) -> 0.90+ confidence.
        """
        if sample_count <= 0:
            return min_confidence

        raw_conf = 1.0 - math.exp(-float(sample_count) / target_scale)
        clamped = min(max_confidence, max(min_confidence, raw_conf))
        return round(clamped, 4)

    @classmethod
    def evaluate_content_completeness(cls, article: Any) -> float:
        """
        Evaluates structural completeness of article body and metadata.
        Does not penalize short breaking news excessively.
        """
        score = 0.0

        title = getattr(article, "title", None)
        if title and len(title.strip()) >= 5:
            score += 0.25

        content = getattr(article, "content", None) or ""
        content_len = len(content.strip())
        if content_len >= 500:
            score += 0.35
        elif content_len >= 150:
            score += 0.25
        elif content_len > 0:
            score += 0.15

        description = getattr(article, "description", None)
        if description and len(description.strip()) >= 20:
            score += 0.15

        author = getattr(article, "author", None)
        if author and len(author.strip()) > 0:
            score += 0.10

        image_url = getattr(article, "image_url", None)
        if image_url and str(image_url).startswith("http"):
            score += 0.10

        canonical_url = getattr(article, "canonical_url", None)
        if canonical_url and str(canonical_url).startswith("http"):
            score += 0.05

        return round(min(1.0, score), 4)

    @classmethod
    def evaluate_extraction_quality(cls, article: Any) -> float:
        """Evaluates content extraction completeness without falsely penalizing paywalls as broken."""
        status = getattr(article, "extraction_status", "COMPLETED")
        if status == "COMPLETED":
            return 1.0
        elif status == "PARTIAL":
            return 0.70
        elif status == "PAYWALL":
            # Valid publisher article behind paywall, still valid metadata
            return 0.50
        elif status == "FAILED":
            return 0.0
        return 0.60

    @classmethod
    def calculate_article_quality(
        cls,
        article: Any,
        source: Optional[Any] = None,
        freshness_score: float = 0.80,
    ) -> Tuple[float, ArticleQualityBreakdown]:
        """
        Computes an aggregated article quality score [0.0, 1.0].
        Source quality is included as a weak Bayesian prior that does not overpower article content.
        """
        completeness = cls.evaluate_content_completeness(article)
        extraction = cls.evaluate_extraction_quality(article)

        # Metadata completeness
        meta_score = 0.0
        if getattr(article, "published_at", None):
            meta_score += 0.40
        if getattr(article, "canonical_url", None):
            meta_score += 0.30
        if getattr(article, "source_name", None) or source:
            meta_score += 0.30
        meta_score = round(min(1.0, meta_score), 4)

        # Source quality prior
        if source:
            src_qual = getattr(source, "quality_score", 0.50)
            src_conf = getattr(source, "quality_confidence", 0.05)
            # Regress toward neutral 0.50 based on confidence
            source_contrib = round((src_qual * src_conf) + (0.50 * (1.0 - src_conf)), 4)
        else:
            source_contrib = 0.50

        # Weighted combination:
        # Completeness: 40%, Extraction: 25%, Metadata: 15%, Source prior: 10%, Freshness: 10%
        final_quality = (
            (completeness * 0.40)
            + (extraction * 0.25)
            + (meta_score * 0.15)
            + (source_contrib * 0.10)
            + (freshness_score * 0.10)
        )
        final_quality = round(min(1.0, max(0.0, final_quality)), 4)

        breakdown = ArticleQualityBreakdown(
            completeness_score=completeness,
            metadata_score=meta_score,
            extraction_score=extraction,
            freshness_score=freshness_score,
            source_quality_contribution=source_contrib,
            final_quality_score=final_quality,
        )

        return final_quality, breakdown
