"""reliability.py — Feed reliability metrics, consecutive failure tracking & health classification."""
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import NewsSource
from app.source_intelligence.models import SourceHealthMetric
from app.source_intelligence.quality_metrics import QualityMetricsCalculator


class SourceReliabilityEngine:
    """Manages source feed reliability, health status tracking, and daily aggregates."""

    @staticmethod
    def classify_health_status(
        is_active: bool,
        fetch_success_rate: float,
        consecutive_failures: int,
    ) -> str:
        """Classifies source health: HEALTHY, DEGRADED, FAILING, INACTIVE."""
        if not is_active:
            return "INACTIVE"
        if consecutive_failures >= 6 or fetch_success_rate < 0.40:
            return "FAILING"
        if consecutive_failures >= 3 or fetch_success_rate < 0.75:
            return "DEGRADED"
        return "HEALTHY"

    @classmethod
    async def record_fetch_event(
        cls,
        session: AsyncSession,
        source_id,
        success: bool,
        error_msg: Optional[str] = None,
        article_count: int = 0,
        duplicate_count: int = 0,
    ) -> SourceHealthMetric:
        """Records a fetch outcome into today's SourceHealthMetric aggregate and updates source health."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        stmt = select(SourceHealthMetric).where(
            SourceHealthMetric.source_id == source_id,
            SourceHealthMetric.date == today_str,
        )
        res = await session.execute(stmt)
        metric = res.scalar_one_or_none()

        if not metric:
            metric = SourceHealthMetric(
                source_id=source_id,
                date=today_str,
                fetch_count=0,
                fetch_success_count=0,
                article_count=0,
                duplicate_count=0,
                extraction_success_count=0,
                extraction_failure_count=0,
                consecutive_failures=0,
            )
            session.add(metric)

        metric.fetch_count += 1
        metric.article_count += article_count
        metric.duplicate_count += duplicate_count

        if success:
            metric.fetch_success_count += 1
            metric.consecutive_failures = 0
        else:
            metric.consecutive_failures += 1

        # Also update NewsSource model fields if found
        stmt_src = select(NewsSource).where(NewsSource.id == source_id)
        res_src = await session.execute(stmt_src)
        source = res_src.scalar_one_or_none()

        if source:
            smoothed_rate = QualityMetricsCalculator.bayesian_smoothed_rate(
                successes=float(metric.fetch_success_count),
                total=float(metric.fetch_count),
                prior_success=9.0,
                prior_total=10.0,
            )
            source.reliability_score = smoothed_rate
            source.health_status = cls.classify_health_status(
                is_active=source.is_active,
                fetch_success_rate=smoothed_rate,
                consecutive_failures=metric.consecutive_failures,
            )

        await session.flush()
        return metric

    @classmethod
    async def record_extraction_event(
        cls,
        session: AsyncSession,
        source_id,
        success: bool,
    ) -> Optional[SourceHealthMetric]:
        """Records an article extraction result into today's SourceHealthMetric."""
        if not source_id:
            return None

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        stmt = select(SourceHealthMetric).where(
            SourceHealthMetric.source_id == source_id,
            SourceHealthMetric.date == today_str,
        )
        res = await session.execute(stmt)
        metric = res.scalar_one_or_none()

        if not metric:
            metric = SourceHealthMetric(
                source_id=source_id,
                date=today_str,
                fetch_count=1,
                fetch_success_count=1,
                article_count=1,
                duplicate_count=0,
                extraction_success_count=0,
                extraction_failure_count=0,
                consecutive_failures=0,
            )
            session.add(metric)

        if success:
            metric.extraction_success_count += 1
        else:
            metric.extraction_failure_count += 1

        # Update source extraction rate
        stmt_src = select(NewsSource).where(NewsSource.id == source_id)
        res_src = await session.execute(stmt_src)
        source = res_src.scalar_one_or_none()

        if source:
            total_ext = metric.extraction_success_count + metric.extraction_failure_count
            source.extraction_success_rate = QualityMetricsCalculator.bayesian_smoothed_rate(
                successes=float(metric.extraction_success_count),
                total=float(total_ext),
                prior_success=10.0,
                prior_total=11.0,
            )

        await session.flush()
        return metric
