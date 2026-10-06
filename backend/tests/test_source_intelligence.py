"""test_source_intelligence.py — Phase 15 Source Intelligence, Reliability & Quality Test Suite.

Tests:
1.  Source evaluation
2.  Source health
3.  Fetch success rate
4.  Extraction success rate
5.  Freshness
6.  Article quality
7.  Quality confidence
8.  Smoothed estimates
9.  New source cold start
10. Duplicate / syndication detection
11. Story coverage
12. Source diversity
13. Conflicting coverage
14. Source follow
15. Source mute
16. Source report
17. Article report
18. User source affinity
19. Source ranking
20. Paywall handling
21. robots.txt compatibility
22. Admin source health
23. Background source evaluation
24. Realistic source test
25. Syndication test
26. Conflict test
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.models.user import User
from app.models.source import NewsSource
from app.models.feed import NewsFeed
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.newspaper.models import StoryCluster, StoryClusterArticle
from app.source_intelligence.models import (
    SourceHealthMetric,
    UserSourcePreference,
    UserSourceAffinity,
    SourceReport,
    ArticleReport,
)
from app.source_intelligence.source_evaluator import SourceEvaluationService
from app.source_intelligence.quality_metrics import QualityMetricsCalculator
from app.source_intelligence.freshness import FreshnessCalculator
from app.source_intelligence.reliability import SourceReliabilityEngine
from app.source_intelligence.diversity import CoverageDiversityEngine
from app.source_intelligence.conflict_detector import ConflictDetector


def _uid():
    return uuid.uuid4()


def _make_user(email_prefix="source_user") -> User:
    return User(
        id=_uid(),
        email=f"{email_prefix}_{_uid().hex[:6]}@example.com",
        password_hash="fakehashedpassword123",
        is_active=True,
    )


def _make_source(name="Test Source", slug=None, quality_score=0.50, is_active=True) -> NewsSource:
    u = _uid().hex[:6]
    return NewsSource(
        id=_uid(),
        name=name,
        slug=slug or f"source-{u}",
        website_url=f"https://{u}.example.com",
        description=f"Description for {name}",
        is_active=is_active,
        quality_score=quality_score,
        quality_confidence=0.05,
        reliability_score=0.50,
        health_status="HEALTHY",
    )


def _make_article(
    source=None,
    title="Test Article",
    content="This is the article full body content with enough detailed information.",
    description="Short description",
    extraction_status="COMPLETED",
    published_at=None,
) -> Article:
    u = _uid().hex[:8]
    return Article(
        id=_uid(),
        title=title,
        slug=f"slug-{u}",
        canonical_url=f"https://example.com/art-{u}",
        source_id=source.id if source else None,
        source_name=source.name if source else "Example Publisher",
        content=content,
        description=description,
        status="PUBLISHED",
        extraction_status=extraction_status,
        published_at=published_at or datetime.now(timezone.utc),
    )


# ===========================================================================
# Unit Tests: Quality Metrics & Bayesian Smoothing
# ===========================================================================
def test_bayesian_smoothed_rate():
    """Test 8: Bayesian smoothing prevents extreme 0% or 100% scores on small samples."""
    # 1 success out of 1 trial should NOT yield 100%
    smoothed_1_1 = QualityMetricsCalculator.bayesian_smoothed_rate(
        successes=1.0, total=1.0, prior_success=8.0, prior_total=10.0
    )
    assert 0.70 <= smoothed_1_1 <= 0.85
    assert smoothed_1_1 != 1.0

    # 0 success out of 1 trial should NOT yield 0%
    smoothed_0_1 = QualityMetricsCalculator.bayesian_smoothed_rate(
        successes=0.0, total=1.0, prior_success=8.0, prior_total=10.0
    )
    assert 0.65 <= smoothed_0_1 <= 0.75
    assert smoothed_0_1 != 0.0

    # 100 successes out of 100 trials converges toward 1.0
    smoothed_100 = QualityMetricsCalculator.bayesian_smoothed_rate(
        successes=100.0, total=100.0, prior_success=8.0, prior_total=10.0
    )
    assert smoothed_100 >= 0.97


def test_quality_confidence_growth():
    """Test 7: Statistical confidence grows smoothly from 0.05 to ~0.95."""
    conf_0 = QualityMetricsCalculator.compute_confidence(0)
    assert conf_0 == 0.05

    conf_5 = QualityMetricsCalculator.compute_confidence(5)
    assert 0.10 <= conf_5 <= 0.20

    conf_40 = QualityMetricsCalculator.compute_confidence(40)
    assert 0.55 <= conf_40 <= 0.70

    conf_150 = QualityMetricsCalculator.compute_confidence(150)
    assert conf_150 >= 0.90


def test_article_quality_calculation():
    """Test 6: Article quality scoring balances completeness, extraction status, and metadata."""
    complete_art = _make_article(
        title="Comprehensive In-Depth Analysis on Semiconductor Supply Chains",
        content="Detailed technical analysis with extensive multi-paragraph explanation " * 20,
        description="Comprehensive summary of supply chain trends in 2026.",
        extraction_status="COMPLETED",
    )
    score_comp, breakdown_comp = QualityMetricsCalculator.calculate_article_quality(complete_art)
    assert score_comp >= 0.75
    assert breakdown_comp.completeness_score >= 0.80
    assert breakdown_comp.extraction_score == 1.0

    # Paywall article should preserve quality metadata without being labeled broken
    paywall_art = _make_article(
        title="Breaking Financial Report Behind Subscriber Paywall",
        content="Subscribers only.",
        description="Detailed market preview.",
        extraction_status="PAYWALL",
    )
    score_paywall, breakdown_paywall = QualityMetricsCalculator.calculate_article_quality(paywall_art)
    assert 0.40 <= score_paywall <= 0.75
    assert breakdown_paywall.extraction_score == 0.50


def test_freshness_decay_and_half_lives():
    """Test 5: Category-aware freshness decay."""
    now = datetime.now(timezone.utc)

    # 24h old breaking news vs 24h old research article
    pub_24h_ago = now - timedelta(hours=24)
    fresh_breaking = FreshnessCalculator.calculate_article_freshness(
        published_at=pub_24h_ago, category="BREAKING", now=now
    )
    fresh_research = FreshnessCalculator.calculate_article_freshness(
        published_at=pub_24h_ago, category="RESEARCH", now=now
    )

    # Breaking news decays faster than research
    assert fresh_breaking < fresh_research
    assert fresh_breaking < 0.25
    assert fresh_research > 0.80


def test_health_status_classification():
    """Test 2: Source health status transitions."""
    assert SourceReliabilityEngine.classify_health_status(is_active=False, fetch_success_rate=0.9, consecutive_failures=0) == "INACTIVE"
    assert SourceReliabilityEngine.classify_health_status(is_active=True, fetch_success_rate=0.95, consecutive_failures=0) == "HEALTHY"
    assert SourceReliabilityEngine.classify_health_status(is_active=True, fetch_success_rate=0.60, consecutive_failures=1) == "DEGRADED"
    assert SourceReliabilityEngine.classify_health_status(is_active=True, fetch_success_rate=0.90, consecutive_failures=4) == "DEGRADED"
    assert SourceReliabilityEngine.classify_health_status(is_active=True, fetch_success_rate=0.30, consecutive_failures=7) == "FAILING"


# ===========================================================================
# Diversity & Syndication Detection Tests
# ===========================================================================
def test_syndication_detection():
    """Test 10 & 25: Syndication detection identifies duplicate wire reprints."""
    wire_text = "WASHINGTON (AP) — Global regulators approved the new safety framework today after extensive consultations."
    art_a = _make_article(title="Regulators approve safety framework", content=wire_text)
    art_a.source_name = "Publisher Alpha"
    art_b = _make_article(title="Safety framework approved by regulators", content=wire_text)
    art_b.source_name = "Publisher Beta"
    art_c = _make_article(title="Analysis: What the new safety framework means", content="A completely independent commentary explaining economic implications.")
    art_c.source_name = "Publisher Gamma"

    assert CoverageDiversityEngine.is_syndicated_copy(art_a, art_b) is True
    assert CoverageDiversityEngine.is_syndicated_copy(art_a, art_c) is False

    # In cluster of 3 articles where A & B are syndicated wire copies:
    total_count, ind_count, div_score, _ = CoverageDiversityEngine.analyze_cluster_coverage([art_a, art_b, art_c])
    assert total_count == 3
    # Independent count should be 2, not 3
    assert ind_count == 2
    assert div_score > 0.0


def test_conflicting_coverage_detection():
    """Test 13 & 26: Conflicting reports flagged as POTENTIAL_CONFLICT without declaring truth."""
    art_a = _make_article(
        title="SuperHeavy Rocket Launch Scheduled for Today",
        description="Officials confirmed the flight test begins this morning.",
    )
    art_b = _make_article(
        title="SuperHeavy Rocket Launch Delayed Due to Technical Glitch",
        description="Engineers announced the flight test is postponed until next week.",
    )
    has_conflict, summary, flag = ConflictDetector.detect_conflicts_in_cluster([art_a, art_b])
    assert has_conflict is True
    assert flag == "POTENTIAL_CONFLICT"
    assert "Different reports detected" in (summary or "")


# ===========================================================================
# Async Database & Service Integration Tests
# ===========================================================================
@pytest.mark.asyncio
async def test_source_evaluation_service(db_session):
    """Test 1 & 9: Source evaluation on new source vs established source."""
    source_est = _make_source("Established Tech News")
    source_new = _make_source("Brand New Blog")
    db_session.add_all([source_est, source_new])
    await db_session.commit()

    # Add 40 successful articles for established source
    for i in range(40):
        art = _make_article(source=source_est, title=f"Tech Story {i}", extraction_status="COMPLETED")
        db_session.add(art)

    # Add 2 articles for new source
    for i in range(2):
        art = _make_article(source=source_new, title=f"Blog Post {i}", extraction_status="COMPLETED")
        db_session.add(art)

    await db_session.commit()

    service = SourceEvaluationService(db_session)
    eval_est = await service.evaluate_source(source_est.id)
    eval_new = await service.evaluate_source(source_new.id)

    assert eval_est is not None
    assert eval_new is not None

    # Established source has high confidence
    assert eval_est.quality_confidence >= 0.60
    assert eval_est.quality_score >= 0.65

    # New source has low confidence and neutral quality prior
    assert eval_new.quality_confidence <= 0.15
    assert 0.45 <= eval_new.quality_score <= 0.60


@pytest.mark.asyncio
async def test_realistic_source_test(db_session):
    """Test 24 (Realistic Source Test): Source A (high success), Source B (lower success), Source C (new cold start)."""
    src_a = _make_source("Source A")
    src_b = _make_source("Source B")
    src_c = _make_source("Source C")
    db_session.add_all([src_a, src_b, src_c])
    await db_session.commit()

    # Source A: 50 articles, 48 completed
    for i in range(50):
        status = "COMPLETED" if i < 48 else "FAILED"
        db_session.add(_make_article(source=src_a, title=f"A Story {i}", extraction_status=status))

    # Source B: 50 articles, 25 completed, 25 failed
    for i in range(50):
        status = "COMPLETED" if i < 25 else "FAILED"
        db_session.add(_make_article(source=src_b, title=f"B Story {i}", extraction_status=status))

    # Source C: 2 articles
    for i in range(2):
        db_session.add(_make_article(source=src_c, title=f"C Story {i}", extraction_status="COMPLETED"))

    await db_session.commit()

    service = SourceEvaluationService(db_session)
    res_a = await service.evaluate_source(src_a.id)
    res_b = await service.evaluate_source(src_b.id)
    res_c = await service.evaluate_source(src_c.id)

    # Source A has high quality & high confidence
    assert res_a.quality_score > res_b.quality_score
    assert res_a.quality_confidence >= 0.70

    # Source B has lower extraction & quality
    assert res_b.extraction_success_rate < res_a.extraction_success_rate

    # Source C remains near neutral with low confidence
    assert res_c.quality_confidence < 0.15
    assert 0.45 <= res_c.quality_score <= 0.60


@pytest.mark.asyncio
async def test_source_follow_and_mute(db_session):
    """Test 14 & 15: Source follow, mute, and preference query."""
    user = _make_user("pref_user")
    source_1 = _make_source("Source To Follow")
    source_2 = _make_source("Source To Mute")
    db_session.add_all([user, source_1, source_2])
    await db_session.commit()

    service = SourceEvaluationService(db_session)
    await service.follow_source(user_id=user.id, source_id=source_1.id)
    await service.mute_source(user_id=user.id, source_id=source_2.id)

    followed, muted = await service.get_user_source_preferences(user.id)
    assert source_1.id in followed
    assert source_2.id in muted
    assert source_1.id not in muted

    # Unmute source 2
    await service.unmute_source(user_id=user.id, source_id=source_2.id)
    _, updated_muted = await service.get_user_source_preferences(user.id)
    assert source_2.id not in updated_muted


@pytest.mark.asyncio
async def test_source_reporting(db_session):
    """Test 16 & 17: User reporting for sources and articles."""
    user = _make_user("reporter")
    source = _make_source("Problematic Source")
    art = _make_article(source=source, title="Article with quality issue")
    db_session.add_all([user, source, art])
    await db_session.commit()

    service = SourceEvaluationService(db_session)
    report_src = await service.report_source(
        source_id=source.id,
        reason="PAYWALL",
        details="Entire feed is locked behind strict paywall",
        user_id=user.id,
    )
    assert report_src.id is not None
    assert report_src.reason == "PAYWALL"
    assert report_src.status == "PENDING"

    report_art = await service.report_article(
        article_id=art.id,
        reason="MISLEADING",
        details="Headline contradicts the body text",
        user_id=user.id,
    )
    assert report_art.id is not None
    assert report_art.reason == "MISLEADING"


@pytest.mark.asyncio
async def test_user_source_affinity_learning(db_session):
    """Test 18: Implicit user source affinity updates incrementally."""
    user = _make_user("affinity_user")
    source = _make_source("Affinity Source")
    db_session.add_all([user, source])
    await db_session.commit()

    service = SourceEvaluationService(db_session)
    aff1 = await service.update_user_source_affinity(user_id=user.id, source_id=source.id, action_weight=0.2)
    score1 = aff1.score
    assert aff1.evidence_count == 1
    assert score1 > 0.50

    aff2 = await service.update_user_source_affinity(user_id=user.id, source_id=source.id, action_weight=0.2)
    assert aff2.evidence_count == 2
    assert aff2.score > score1


@pytest.mark.asyncio
async def test_story_coverage_endpoint(db_session):
    """Test 11 & 12: Story cluster coverage retrieval and variants."""
    source_a = _make_source("Publisher Alpha")
    source_b = _make_source("Publisher Beta")
    art_a = _make_article(source=source_a, title="Major Space Mission Launch Approved")
    art_b = _make_article(source=source_b, title="Space Mission Launch Given Full Approval")
    db_session.add_all([source_a, source_b, art_a, art_b])
    await db_session.commit()

    # Link in cluster
    cluster = StoryCluster(id=_uid(), cluster_key=f"cluster-{_uid().hex[:8]}")
    db_session.add(cluster)
    await db_session.flush()

    sca_a = StoryClusterArticle(cluster_id=cluster.id, article_id=art_a.id, is_primary=True)
    sca_b = StoryClusterArticle(cluster_id=cluster.id, article_id=art_b.id, is_primary=False)
    db_session.add_all([sca_a, sca_b])
    await db_session.commit()

    service = SourceEvaluationService(db_session)
    coverage = await service.get_story_coverage(art_a.id)

    assert coverage.total_coverage_count == 2
    assert coverage.independent_sources_count >= 1
    assert len(coverage.variants) == 2


@pytest.mark.asyncio
async def test_admin_source_health(db_session):
    """Test 22: Admin source health summary."""
    s1 = _make_source("Admin Source 1")
    s2 = _make_source("Admin Source 2", is_active=False)
    db_session.add_all([s1, s2])
    await db_session.commit()

    service = SourceEvaluationService(db_session)
    admin_health = await service.get_admin_source_health()

    assert admin_health.total_sources >= 2
    assert admin_health.inactive_count >= 1


@pytest.mark.asyncio
async def test_source_ranking_dominance(db_session):
    """Test 19 & Personalization Test: Personal relevance remains dominant over source quality."""
    from app.personalization.scoring.relevance_scorer import RelevanceScorer
    from app.models.topic import Topic

    scorer = RelevanceScorer()
    ai_top = Topic(id=_uid(), name="Artificial Intelligence", slug="artificial-intelligence")
    cooking_top = Topic(id=_uid(), name="Cooking", slug="cooking")

    # Article 1: Highly relevant AI article from lower-confidence source
    art_ai = _make_article(title="New LLM Reasoning Breakthrough in AI", description="Artificial intelligence models advance.")
    art_ai.topics = [ai_top]
    score_ai, breakdown_ai = scorer.compute_relevance(
        art_ai,
        positive_interests={"artificial-intelligence": 0.95},
        negative_interests={"cooking": 0.90},
    )

    # Article 2: Completely irrelevant cooking article from high-quality source
    art_cooking = _make_article(title="Best Traditional Pasta Recipes", description="Authentic cooking guide.")
    art_cooking.topics = [cooking_top]
    score_cooking, breakdown_cooking = scorer.compute_relevance(
        art_cooking,
        positive_interests={"artificial-intelligence": 0.95},
        negative_interests={"cooking": 0.90},
    )

    assert score_ai > score_cooking
    assert score_ai >= 0.30
    assert score_cooking <= 0.20


@pytest.mark.asyncio
async def test_paywall_handling():
    """Test 20: Paywall articles retain metadata without pretending full text is available."""
    art = _make_article(
        title="Exclusive Investigation Into Private Tech Valuations",
        content="This content is available to subscribers only.",
        description="Behind the scenes of tech unicorn valuations.",
        extraction_status="PAYWALL",
    )
    score, breakdown = QualityMetricsCalculator.calculate_article_quality(art)
    assert breakdown.extraction_score == 0.50
    assert breakdown.completeness_score > 0.30
    assert score >= 0.40


@pytest.mark.asyncio
async def test_background_source_evaluation_job(db_session):
    """Test 23: Background worker job evaluates all sources."""
    s1 = _make_source("Scheduled Source 1")
    s2 = _make_source("Scheduled Source 2")
    db_session.add_all([s1, s2])
    await db_session.commit()

    service = SourceEvaluationService(db_session)
    evaluated = await service.evaluate_all_sources()
    assert len(evaluated) >= 2

