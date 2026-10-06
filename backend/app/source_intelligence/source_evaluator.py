"""source_evaluator.py — Main SourceEvaluationService orchestrator."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, func, desc, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import NewsSource
from app.models.feed import NewsFeed
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.newspaper.models import StoryCluster, StoryClusterArticle
from app.newspaper.story_clusterer import StoryClusterer
from app.source_intelligence.models import (
    SourceHealthMetric,
    UserSourcePreference,
    UserSourceAffinity,
    SourceReport,
    ArticleReport,
)
from app.source_intelligence.quality_metrics import QualityMetricsCalculator
from app.source_intelligence.freshness import FreshnessCalculator
from app.source_intelligence.reliability import SourceReliabilityEngine
from app.source_intelligence.diversity import CoverageDiversityEngine
from app.source_intelligence.conflict_detector import ConflictDetector
from app.source_intelligence.schemas import (
    SourceItem,
    SourceDetail,
    StoryCoverageResponse,
    ArticleCoverageItem,
    AdminSourceHealthResponse,
    SourceHealthResponseItem,
)


class SourceEvaluationService:
    """Core service for evaluating news sources, managing preferences, and analyzing coverage."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate_source(self, source_id: uuid.UUID) -> Optional[NewsSource]:
        """
        Evaluates observable metrics for a specific source and updates its quality profile.
        Uses Bayesian smoothed priors to ensure cold-start new sources start neutral with low confidence.
        """
        stmt = select(NewsSource).where(NewsSource.id == source_id)
        res = await self.session.execute(stmt)
        source = res.scalar_one_or_none()
        if not source:
            return None

        # 1. Total article count & extraction statistics
        stmt_arts = select(
            func.count(Article.id),
            func.sum(case((Article.extraction_status == "COMPLETED", 1), else_=0)),
            func.sum(case((Article.extraction_status == "FAILED", 1), else_=0)),
            func.max(Article.published_at),
        ).where(Article.source_id == source_id)
        res_arts = await self.session.execute(stmt_arts)
        art_count, ext_completed, ext_failed, latest_pub = res_arts.one()

        art_count = art_count or 0
        ext_completed = ext_completed or 0
        ext_failed = ext_failed or 0

        # 2. Health metrics aggregates from last 30 days
        stmt_metrics = select(
            func.sum(SourceHealthMetric.fetch_count),
            func.sum(SourceHealthMetric.fetch_success_count),
            func.sum(SourceHealthMetric.duplicate_count),
            func.sum(SourceHealthMetric.consecutive_failures),
        ).where(SourceHealthMetric.source_id == source_id)
        res_metrics = await self.session.execute(stmt_metrics)
        fetch_total, fetch_success, dup_count, max_consec_fail = res_metrics.one()

        fetch_total = fetch_total or 0
        fetch_success = fetch_success or 0
        dup_count = dup_count or 0
        max_consec_fail = max_consec_fail or 0

        # 3. Calculate Bayesian smoothed rates
        ext_success_rate = QualityMetricsCalculator.bayesian_smoothed_rate(
            successes=float(ext_completed),
            total=float(ext_completed + ext_failed),
            prior_success=10.0,
            prior_total=11.0,
        )

        rel_score = QualityMetricsCalculator.bayesian_smoothed_rate(
            successes=float(fetch_success),
            total=float(fetch_total),
            prior_success=8.0,
            prior_total=10.0,
        )

        dup_rate = round(float(dup_count) / float(art_count + 10.0), 4)

        # 4. Freshness
        freshness_score = FreshnessCalculator.calculate_source_freshness(
            last_published_at=latest_pub,
            article_count_last_7_days=art_count,
        )

        # 5. Statistical confidence based on article volume
        confidence = QualityMetricsCalculator.compute_confidence(
            sample_count=art_count,
            target_scale=40.0,
            min_confidence=0.05,
            max_confidence=0.95,
        )

        # 6. Overall Quality Score
        raw_quality = (
            (ext_success_rate * 0.40)
            + (rel_score * 0.25)
            + (freshness_score * 0.20)
            + ((1.0 - min(1.0, dup_rate)) * 0.15)
        )
        # Regress with confidence toward neutral 0.50
        quality_score = round((raw_quality * confidence) + (0.50 * (1.0 - confidence)), 4)

        # 7. Health status classification
        health_status = SourceReliabilityEngine.classify_health_status(
            is_active=source.is_active,
            fetch_success_rate=rel_score,
            consecutive_failures=max_consec_fail,
        )

        # Update model
        source.quality_score = quality_score
        source.quality_confidence = confidence
        source.reliability_score = rel_score
        source.freshness_score = freshness_score
        source.coverage_score = round(min(1.0, float(art_count) / 100.0), 4)
        source.extraction_success_rate = ext_success_rate
        source.duplicate_rate = dup_rate
        source.health_status = health_status
        source.last_evaluated_at = datetime.now(timezone.utc)
        source.evaluation_version = (source.evaluation_version or 1) + 1

        await self.session.commit()
        return source

    async def evaluate_all_sources(self) -> List[NewsSource]:
        """Evaluates all registered news sources."""
        stmt = select(NewsSource.id)
        res = await self.session.execute(stmt)
        source_ids = res.scalars().all()

        evaluated = []
        for sid in source_ids:
            s = await self.evaluate_source(sid)
            if s:
                evaluated.append(s)
        return evaluated

    async def get_source_detail(
        self,
        source_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Optional[SourceDetail]:
        """Returns comprehensive detail for a news source without exposing internal formulas."""
        stmt = select(NewsSource).where(NewsSource.id == source_id)
        res = await self.session.execute(stmt)
        source = res.scalar_one_or_none()
        if not source:
            return None

        # Fetch recent articles
        stmt_arts = (
            select(Article)
            .where(Article.source_id == source_id)
            .order_by(desc(Article.published_at))
            .limit(10)
        )
        res_arts = await self.session.execute(stmt_arts)
        articles = res_arts.scalars().all()

        # Count total articles
        stmt_count = select(func.count(Article.id)).where(Article.source_id == source_id)
        total_arts = (await self.session.execute(stmt_count)).scalar() or 0

        # Feed count
        stmt_feeds = select(func.count(NewsFeed.id)).where(NewsFeed.source_id == source_id)
        feed_count = (await self.session.execute(stmt_feeds)).scalar() or 0

        # User preferences
        is_following = False
        is_muted = False
        if user_id:
            stmt_pref = select(UserSourcePreference).where(
                UserSourcePreference.user_id == user_id,
                UserSourcePreference.source_id == source_id,
            )
            pref = (await self.session.execute(stmt_pref)).scalar_one_or_none()
            if pref:
                is_following = pref.is_following
                is_muted = pref.is_muted

        recent_art_data = [
            {
                "id": str(a.id),
                "title": a.title,
                "slug": a.slug,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "reading_time_minutes": a.reading_time_minutes or 3,
                "extraction_status": a.extraction_status or "COMPLETED",
            }
            for a in articles
        ]

        latest_update = articles[0].published_at if articles else source.updated_at

        return SourceDetail(
            id=source.id,
            name=source.name,
            slug=source.slug,
            website_url=source.website_url,
            description=source.description,
            logo_url=source.logo_url,
            is_active=source.is_active,
            health_status=source.health_status or "HEALTHY",
            freshness_score=source.freshness_score or 0.50,
            quality_score=source.quality_score or 0.50,
            quality_confidence=source.quality_confidence or 0.05,
            reliability_score=source.reliability_score or 0.50,
            coverage_score=source.coverage_score or 0.50,
            extraction_success_rate=source.extraction_success_rate or 1.0,
            duplicate_rate=source.duplicate_rate or 0.0,
            article_count=total_arts,
            is_following=is_following,
            is_muted=is_muted,
            last_evaluated_at=source.last_evaluated_at,
            recent_articles=recent_art_data,
            topics_covered=["News", "General"],
            latest_update=latest_update,
            feed_count=feed_count,
            daily_article_average=round(float(total_arts) / 30.0, 1),
        )

    # -----------------------------------------------------------------------
    # User Preferences: Follow / Mute / Reporting
    # -----------------------------------------------------------------------
    async def follow_source(self, user_id: uuid.UUID, source_id: uuid.UUID) -> bool:
        stmt = select(UserSourcePreference).where(
            UserSourcePreference.user_id == user_id,
            UserSourcePreference.source_id == source_id,
        )
        res = await self.session.execute(stmt)
        pref = res.scalar_one_or_none()

        if not pref:
            pref = UserSourcePreference(
                user_id=user_id,
                source_id=source_id,
                is_following=True,
                is_muted=False,
            )
            self.session.add(pref)
        else:
            pref.is_following = True
            pref.is_muted = False
            pref.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        return True

    async def unfollow_source(self, user_id: uuid.UUID, source_id: uuid.UUID) -> bool:
        stmt = select(UserSourcePreference).where(
            UserSourcePreference.user_id == user_id,
            UserSourcePreference.source_id == source_id,
        )
        res = await self.session.execute(stmt)
        pref = res.scalar_one_or_none()

        if pref:
            pref.is_following = False
            pref.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
        return True

    async def mute_source(self, user_id: uuid.UUID, source_id: uuid.UUID) -> bool:
        stmt = select(UserSourcePreference).where(
            UserSourcePreference.user_id == user_id,
            UserSourcePreference.source_id == source_id,
        )
        res = await self.session.execute(stmt)
        pref = res.scalar_one_or_none()

        if not pref:
            pref = UserSourcePreference(
                user_id=user_id,
                source_id=source_id,
                is_following=False,
                is_muted=True,
            )
            self.session.add(pref)
        else:
            pref.is_muted = True
            pref.is_following = False
            pref.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        return True

    async def unmute_source(self, user_id: uuid.UUID, source_id: uuid.UUID) -> bool:
        stmt = select(UserSourcePreference).where(
            UserSourcePreference.user_id == user_id,
            UserSourcePreference.source_id == source_id,
        )
        res = await self.session.execute(stmt)
        pref = res.scalar_one_or_none()

        if pref:
            pref.is_muted = False
            pref.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
        return True

    async def report_source(
        self,
        source_id: uuid.UUID,
        reason: str,
        details: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> SourceReport:
        report = SourceReport(
            source_id=source_id,
            user_id=user_id,
            reason=reason,
            details=details,
            status="PENDING",
        )
        self.session.add(report)
        await self.session.commit()
        return report

    async def report_article(
        self,
        article_id: uuid.UUID,
        reason: str,
        details: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> ArticleReport:
        report = ArticleReport(
            article_id=article_id,
            user_id=user_id,
            reason=reason,
            details=details,
            status="PENDING",
        )
        self.session.add(report)
        await self.session.commit()
        return report

    async def get_user_source_preferences(
        self,
        user_id: uuid.UUID,
    ) -> Tuple[List[uuid.UUID], List[uuid.UUID]]:
        """Returns (followed_source_ids, muted_source_ids)."""
        stmt = select(UserSourcePreference).where(UserSourcePreference.user_id == user_id)
        res = await self.session.execute(stmt)
        prefs = res.scalars().all()

        followed = [p.source_id for p in prefs if p.is_following]
        muted = [p.source_id for p in prefs if p.is_muted]
        return followed, muted

    async def update_user_source_affinity(
        self,
        user_id: uuid.UUID,
        source_id: uuid.UUID,
        action_weight: float = 0.10,
    ) -> UserSourceAffinity:
        """Incrementally updates user source affinity based on actual reading behavior."""
        stmt = select(UserSourceAffinity).where(
            UserSourceAffinity.user_id == user_id,
            UserSourceAffinity.source_id == source_id,
        )
        res = await self.session.execute(stmt)
        affinity = res.scalar_one_or_none()

        if not affinity:
            affinity = UserSourceAffinity(
                user_id=user_id,
                source_id=source_id,
                score=0.50 + (action_weight * 0.20),
                confidence=0.15,
                evidence_count=1,
            )
            self.session.add(affinity)
        else:
            affinity.evidence_count += 1
            # Moving average
            affinity.score = min(1.0, affinity.score + (action_weight * (1.0 - affinity.score) * 0.20))
            affinity.confidence = min(0.95, affinity.confidence + 0.05)
            affinity.last_updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        return affinity

    # -----------------------------------------------------------------------
    # Multi-Perspective Story Coverage
    # -----------------------------------------------------------------------
    async def get_story_coverage(self, article_id: uuid.UUID) -> StoryCoverageResponse:
        """
        Retrieves all perspective articles in the same story cluster,
        detects syndication reprints vs independent reports,
        and checks for potential conflicting coverage.
        """
        stmt_art = select(Article).where(Article.id == article_id)
        res_art = await self.session.execute(stmt_art)
        primary_article = res_art.scalar_one_or_none()
        if not primary_article:
            return StoryCoverageResponse(
                primary_article_id=article_id,
                total_coverage_count=0,
                independent_sources_count=0,
                coverage_diversity_score=0.0,
                has_conflicts=False,
                variants=[],
            )

        # 1. Find cluster containing this article
        stmt_cluster = select(StoryClusterArticle).where(StoryClusterArticle.article_id == article_id)
        res_cluster = await self.session.execute(stmt_cluster)
        sca_entry = res_cluster.scalar_one_or_none()

        cluster_articles: List[Article] = []
        cluster_id = None

        if sca_entry:
            cluster_id = sca_entry.cluster_id
            stmt_all_sca = (
                select(Article)
                .join(StoryClusterArticle, StoryClusterArticle.article_id == Article.id)
                .where(StoryClusterArticle.cluster_id == cluster_id)
            )
            res_all_sca = await self.session.execute(stmt_all_sca)
            cluster_articles = res_all_sca.scalars().all()

        if not cluster_articles:
            # Dynamic candidate search for similar articles if no cluster registered
            stmt_recent = (
                select(Article)
                .where(
                    Article.id != article_id,
                    Article.status == "PUBLISHED",
                    Article.published_at >= (primary_article.published_at or datetime.now(timezone.utc)) - timedelta(days=2),
                )
                .limit(20)
            )
            recent_candidates = (await self.session.execute(stmt_recent)).scalars().all()
            clusterer = StoryClusterer(self.session)
            matching = [primary_article]
            for c in recent_candidates:
                sim, _ = clusterer.are_stories_similar(primary_article, c)
                if sim:
                    matching.append(c)
            cluster_articles = matching

        # 2. Analyze diversity & syndication
        total_count, ind_count, div_score, meta_items = CoverageDiversityEngine.analyze_cluster_coverage(cluster_articles)

        # 3. Detect potential conflicts
        has_conflicts, conflict_summary, conflict_flag = ConflictDetector.detect_conflicts_in_cluster(cluster_articles)

        # 4. Construct variant items
        variants: List[ArticleCoverageItem] = []
        for item in meta_items:
            art = item["article"]
            is_prim = (art.id == primary_article.id)
            qual_score, _ = QualityMetricsCalculator.calculate_article_quality(art)
            variants.append(
                ArticleCoverageItem(
                    article_id=art.id,
                    title=art.title,
                    slug=art.slug,
                    source_id=art.source_id,
                    source_name=art.source_name or "Independent Source",
                    source_url=art.source_url,
                    published_at=art.published_at,
                    is_syndicated=item["is_syndicated"],
                    is_primary=is_prim,
                    quality_score=qual_score,
                    summary=art.description,
                    reading_time_minutes=art.reading_time_minutes or 3,
                    extraction_status=art.extraction_status or "COMPLETED",
                )
            )

        return StoryCoverageResponse(
            cluster_id=cluster_id,
            primary_article_id=primary_article.id,
            total_coverage_count=total_count,
            independent_sources_count=ind_count,
            coverage_diversity_score=div_score,
            has_conflicts=has_conflicts,
            conflict_summary=conflict_summary,
            conflict_flag=conflict_flag,
            variants=variants,
        )

    # -----------------------------------------------------------------------
    # Admin Source Health
    # -----------------------------------------------------------------------
    async def get_admin_source_health(self) -> AdminSourceHealthResponse:
        """Provides aggregate operational health data for administrator / development visibility."""
        stmt = select(NewsSource)
        res = await self.session.execute(stmt)
        sources = res.scalars().all()

        items: List[SourceHealthResponseItem] = []
        healthy = 0
        degraded = 0
        failing = 0
        inactive = 0

        for s in sources:
            status = s.health_status or "HEALTHY"
            if not s.is_active:
                status = "INACTIVE"

            if status == "HEALTHY":
                healthy += 1
            elif status == "DEGRADED":
                degraded += 1
            elif status == "FAILING":
                failing += 1
            elif status == "INACTIVE":
                inactive += 1

            items.append(
                SourceHealthResponseItem(
                    source_id=s.id,
                    source_name=s.name,
                    health_status=status,
                    fetch_count=0,
                    fetch_success_count=0,
                    fetch_success_rate=s.reliability_score or 0.50,
                    extraction_success_rate=s.extraction_success_rate or 1.0,
                    duplicate_rate=s.duplicate_rate or 0.0,
                    consecutive_failures=0,
                    last_success_at=s.updated_at,
                    quality_score=s.quality_score or 0.50,
                    quality_confidence=s.quality_confidence or 0.05,
                )
            )

        return AdminSourceHealthResponse(
            total_sources=len(sources),
            healthy_count=healthy,
            degraded_count=degraded,
            failing_count=failing,
            inactive_count=inactive,
            sources=items,
        )
