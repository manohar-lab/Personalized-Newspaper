"""test_story_intelligence.py — Phase 16 Multi-Source Story Intelligence Engine Test Suite."""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.models.user import User
from app.models.topic import Topic
from app.models.entity import Entity
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.story_intelligence.models import Story, StoryArticle, StoryMergeEvent
from app.story_intelligence.story_service import StoryIntelligenceService
from app.story_intelligence.story_matcher import StoryMatcher
from app.story_intelligence.story_summarizer import StorySummarizer
from app.story_intelligence.story_lifecycle import StoryLifecycleManager


def _uid():
    return uuid.uuid4()


def _now():
    return datetime.now(timezone.utc)


def _vec(dim: int) -> list:
    """Generates orthogonal one-hot mock embedding vector for isolated test clustering."""
    v = [0.0] * 384
    v[dim % 384] = 1.0
    return v


@pytest.mark.asyncio
async def test_story_creation_and_ingestion(db_session):
    """Test 1 & 4: Ingesting an initial article creates a new Story."""
    service = StoryIntelligenceService(db_session)

    art = Article(
        id=_uid(),
        title="OpenAI Announces New GPT Reasoning Model",
        slug="openai-announces-new-gpt-reasoning-model-1",
        description="OpenAI releases its newest reasoning model with advanced coding benchmarks.",
        content="Full article text about the launch of the new reasoning model.",
        status="PUBLISHED",
        published_at=_now(),
    )
    analysis = ArticleAnalysis(
        id=_uid(),
        article_id=art.id,
        summary="OpenAI announced a new reasoning system designed for complex problem-solving.",
        primary_category="TECHNOLOGY",
        importance_score=0.85,
        article_quality_score=0.90,
        embedding=_vec(1),
    )
    db_session.add_all([art, analysis])
    await db_session.commit()

    story, story_art, is_new = await service.ingest_article_into_story(art.id)
    await db_session.commit()

    assert is_new is True
    assert story is not None
    assert story.article_count == 1
    assert story.source_count == 1
    assert story.primary_article_id == art.id
    assert story_art.relationship_type == "PRIMARY"
    assert "OpenAI Announces New GPT Reasoning Model" in story.title


@pytest.mark.asyncio
async def test_story_matching_and_article_assignment(db_session):
    """Test 2 & 3: Matching a subsequent article to an existing story cluster."""
    service = StoryIntelligenceService(db_session)

    # Article 1: Initial report
    art1 = Article(
        id=_uid(),
        title="NVIDIA Unveils Next-Gen AI GPU Architecture Today",
        slug="nvidia-unveils-gpu-architecture-today-1",
        description="NVIDIA launches breakthrough GPU architecture.",
        content="Initial report on NVIDIA's breakthrough architecture.",
        status="PUBLISHED",
        published_at=_now() - timedelta(hours=2),
    )
    analysis1 = ArticleAnalysis(
        id=_uid(),
        article_id=art1.id,
        summary="NVIDIA launches breakthrough GPU architecture.",
        embedding=_vec(2),
    )
    db_session.add_all([art1, analysis1])
    await db_session.commit()

    story1, _, is_new1 = await service.ingest_article_into_story(art1.id)
    await db_session.commit()
    assert is_new1 is True

    # Article 2: Follow-up technical details (same story)
    art2 = Article(
        id=_uid(),
        title="NVIDIA Releases Technical Architecture Details for New AI GPU",
        slug="nvidia-releases-technical-architecture-details-2",
        description="Technical analysis of NVIDIA GPU architecture.",
        content="Deep dive into the architecture and benchmarks of the new GPU.",
        status="PUBLISHED",
        published_at=_now() - timedelta(minutes=30),
    )
    analysis2 = ArticleAnalysis(
        id=_uid(),
        article_id=art2.id,
        summary="Technical analysis of NVIDIA GPU architecture.",
        embedding=_vec(2),
    )
    db_session.add_all([art2, analysis2])
    await db_session.commit()

    story2, story_art2, is_new2 = await service.ingest_article_into_story(art2.id)
    await db_session.commit()

    assert is_new2 is False
    assert story2.id == story1.id
    assert story2.article_count == 2
    assert story_art2.relationship_type in ["UPDATE", "ANALYSIS"]


@pytest.mark.asyncio
async def test_story_title_and_summary_synthesis(db_session):
    """Test 10 & 11: Editorial title cleaning and synthesized multi-source summary."""
    title = "BREAKING: OpenAI Announces Next-Gen Model - TechCrunch"
    cleaned = StorySummarizer.clean_editorial_title(title)
    assert cleaned == "OpenAI Announces Next-Gen Model"

    art1 = Article(
        id=_uid(),
        title="OpenAI Announces Next-Gen Model",
        slug="openai-synth-1",
        description="OpenAI revealed its next-generation reasoning AI today.",
    )
    art2 = Article(
        id=_uid(),
        title="Experts React to OpenAI Model",
        slug="openai-synth-2",
        description="Industry analysts noted the reasoning performance benchmarks surpass previous standards.",
    )

    synth = StorySummarizer.synthesize_story_summary([art1, art2])
    assert "OpenAI" in synth
    assert "reports" in synth or "reactions" in synth or "analysts" in synth


@pytest.mark.asyncio
async def test_story_merging_and_event_history(db_session):
    """Test 8 & 9: Merging two duplicate stories preserves history and reassigns articles."""
    service = StoryIntelligenceService(db_session)

    # Story A
    artA = Article(
        id=_uid(),
        title="SpaceX Launches Falcon Heavy Mission",
        slug="spacex-launches-falcon-heavy-a",
        content="Falcon heavy launch successful.",
        status="PUBLISHED",
        published_at=_now(),
    )
    anaA = ArticleAnalysis(id=_uid(), article_id=artA.id, embedding=_vec(3))
    db_session.add_all([artA, anaA])
    await db_session.commit()
    storyA, _, _ = await service.ingest_article_into_story(artA.id)
    await db_session.commit()

    # Story B
    artB = Article(
        id=_uid(),
        title="Falcon Heavy Rocket Liftoff From Cape Canaveral",
        slug="falcon-heavy-liftoff-b",
        content="SpaceX liftoff went smoothly today.",
        status="PUBLISHED",
        published_at=_now(),
    )
    anaB = ArticleAnalysis(id=_uid(), article_id=artB.id, embedding=_vec(4))
    db_session.add_all([artB, anaB])
    await db_session.commit()
    storyB, _, _ = await service.ingest_article_into_story(artB.id)
    await db_session.commit()

    assert storyA.id != storyB.id

    # Merge Story B into Story A
    merged_target = await service.merge_stories(
        source_story_id=storyB.id,
        target_story_id=storyA.id,
        reason="Identified duplicate rocket launch coverage",
    )
    await db_session.commit()

    assert merged_target.id == storyA.id
    assert merged_target.article_count == 2

    # Check merge event
    stmt_ev = select(StoryMergeEvent).where(StoryMergeEvent.source_story_id == storyB.id)
    res_ev = await db_session.execute(stmt_ev)
    event = res_ev.scalar_one_or_none()
    assert event is not None
    assert event.target_story_id == storyA.id

    # Check redirect on fetch
    fetched = await service.get_story_by_id_or_slug(str(storyB.id))
    assert fetched.id == storyA.id


@pytest.mark.asyncio
async def test_primary_and_latest_article_selection(db_session):
    """Test 13 & 14: Primary foundational article vs latest update selection."""
    t0 = _now() - timedelta(hours=5)
    t1 = _now() - timedelta(hours=1)

    art_early = Article(
        id=_uid(),
        title="Initial Launch Announcement",
        content="Extensive in-depth report on the mission architecture with 1000 words.",
        published_at=t0,
    )
    ana_early = ArticleAnalysis(
        id=_uid(),
        article_id=art_early.id,
        article_quality_score=0.95,
    )
    art_early.analysis = ana_early

    art_late = Article(
        id=_uid(),
        title="Brief Mission Update",
        content="Quick 200-word status update.",
        published_at=t1,
    )
    ana_late = ArticleAnalysis(
        id=_uid(),
        article_id=art_late.id,
        article_quality_score=0.60,
    )
    art_late.analysis = ana_late

    articles = [art_early, art_late]

    primary = StoryLifecycleManager.select_primary_article(articles)
    latest = StoryLifecycleManager.select_latest_article(articles)

    assert primary.id == art_early.id
    assert latest.id == art_late.id


@pytest.mark.asyncio
async def test_independent_source_count_and_syndication(db_session):
    """Test 17 & 18: Syndicated duplicate articles do not inflate independent source count."""
    shared_text = "The Federal Reserve held interest rates steady today citing balanced economic indicators."

    art1 = Article(
        id=_uid(),
        title="Fed Holds Interest Rates Steady",
        content=shared_text,
        source_name="Publisher A",
        published_at=_now(),
    )
    art2 = Article(
        id=_uid(),
        title="Fed Decides to Keep Interest Rates Steady",
        content=shared_text,  # Syndicated identical wire copy
        source_name="Publisher B",
        published_at=_now(),
    )
    art3 = Article(
        id=_uid(),
        title="Federal Reserve Keeps Rates Constant in Latest Decision",
        content=shared_text,  # Syndicated identical wire copy
        source_name="Publisher C",
        published_at=_now(),
    )
    art4 = Article(
        id=_uid(),
        title="Economic Analysis: What the Fed Rate Decision Means for Mortgages",
        content="Mortgage rates are expected to stabilize over the next quarter following the Fed's commentary.",
        source_name="Publisher D",
        published_at=_now(),
    )

    articles = [art1, art2, art3, art4]
    total_sources, indep_sources, sources_list = StoryLifecycleManager.compute_independent_source_count(articles)

    assert total_sources == 4
    # Despite 4 publishers, arts 1, 2, 3 are syndicated copies -> only 2 independent reports!
    assert indep_sources == 2
    assert len(sources_list) == 4


@pytest.mark.asyncio
async def test_conflicting_coverage_detection(db_session):
    """Test 19: Detecting potential conflict between contradictory reports."""
    service = StoryIntelligenceService(db_session)

    emb = _vec(5)

    art1 = Article(
        id=_uid(),
        title="Company Confirms Product Launches Today",
        slug="company-confirms-launch-today-1",
        description="Company confirms product launch.",
        content="The company confirmed the official launch is proceeding today as planned.",
        source_name="Source A",
        status="PUBLISHED",
        published_at=_now() - timedelta(hours=2),
    )
    ana1 = ArticleAnalysis(id=_uid(), article_id=art1.id, embedding=emb)
    art1.analysis = ana1

    art2 = Article(
        id=_uid(),
        title="Company Delays Product Launch Amid Technical Issues",
        slug="company-delays-product-launch-2",
        description="Company delays product launch.",
        content="Reports indicate the product launch has been delayed following unexpected technical setbacks.",
        source_name="Source B",
        status="PUBLISHED",
        published_at=_now() - timedelta(hours=1),
    )
    ana2 = ArticleAnalysis(id=_uid(), article_id=art2.id, embedding=emb)
    art2.analysis = ana2

    db_session.add_all([art1, art2, ana1, ana2])
    await db_session.commit()

    story, _, _ = await service.ingest_article_into_story(art1.id)
    await db_session.commit()
    await service.ingest_article_into_story(art2.id)
    await db_session.commit()

    detail = await service.get_story_detail(str(story.id))
    assert detail is not None
    # Potential conflict should be detected and surfaced without declaring false
    assert detail.has_conflicts is True
    assert detail.conflict_note is not None


@pytest.mark.asyncio
async def test_developing_story_detection_and_timeline(db_session):
    """Test 15, 20 & 21: Rapid multi-source updates trigger DEVELOPING status and ordered timeline."""
    service = StoryIntelligenceService(db_session)

    t0 = _now() - timedelta(hours=2)
    t1 = _now() - timedelta(hours=1)
    t2 = _now() - timedelta(minutes=15)
    sat_emb = _vec(6)

    art1 = Article(
        id=_uid(),
        title="Space Agency Confirms Satellite Anomaly",
        slug="satellite-anomaly-1",
        content="Telemetry issue observed.",
        status="PUBLISHED",
        published_at=t0,
    )
    ana1 = ArticleAnalysis(id=_uid(), article_id=art1.id, embedding=sat_emb)
    art1.analysis = ana1

    art2 = Article(
        id=_uid(),
        title="Engineers Restore Communications With Satellite",
        slug="satellite-restored-2",
        content="Communications recovered.",
        status="PUBLISHED",
        published_at=t1,
    )
    ana2 = ArticleAnalysis(id=_uid(), article_id=art2.id, embedding=sat_emb)
    art2.analysis = ana2

    art3 = Article(
        id=_uid(),
        title="Official Mission Status Report Released",
        slug="satellite-status-report-3",
        content="Full status report on orbit stabilization.",
        status="PUBLISHED",
        published_at=t2,
    )
    ana3 = ArticleAnalysis(id=_uid(), article_id=art3.id, embedding=sat_emb)
    art3.analysis = ana3

    db_session.add_all([art1, art2, art3, ana1, ana2, ana3])
    await db_session.commit()

    story, _, is_n1 = await service.ingest_article_into_story(art1.id)
    await db_session.commit()
    assert is_n1 is True

    _, _, is_n2 = await service.ingest_article_into_story(art2.id)
    await db_session.commit()
    assert is_n2 is False

    _, _, is_n3 = await service.ingest_article_into_story(art3.id)
    await db_session.commit()
    assert is_n3 is False

    detail = await service.get_story_detail(str(story.id))
    assert detail.status == "DEVELOPING"
    assert len(detail.timeline) == 3
    # Verify chronological ordering
    assert detail.timeline[0].article_id == art1.id
    assert detail.timeline[1].article_id == art2.id
    assert detail.timeline[2].article_id == art3.id


@pytest.mark.asyncio
async def test_realistic_multi_source_story_clustering(db_session):
    """
    Realistic Test Requirement:
    Articles 1–4 belong to SAME STORY (announcement, technical details, expert reaction, CEO discussion).
    Article 5 belongs to a DIFFERENT STORY (unrelated competing model).
    """
    service = StoryIntelligenceService(db_session)

    # Shared entities & semantics for OpenAI Model (dim 7) vs Robotics Startup (dim 8)
    shared_emb = _vec(7)
    unrelated_emb = _vec(8)

    art1 = Article(
        id=_uid(),
        title="AI Startup Announces Next-Gen Reasoning Model",
        slug="ai-startup-announces-reasoning-model",
        content="Company announced their next-generation reasoning model.",
        status="PUBLISHED",
        published_at=_now() - timedelta(hours=4),
    )
    ana1 = ArticleAnalysis(id=_uid(), article_id=art1.id, embedding=shared_emb)
    art1.analysis = ana1

    art2 = Article(
        id=_uid(),
        title="AI Startup Releases Technical Details on Reasoning Model",
        slug="ai-startup-releases-technical-details",
        content="Technical benchmark results and architecture of the newly announced model.",
        status="PUBLISHED",
        published_at=_now() - timedelta(hours=3),
    )
    ana2 = ArticleAnalysis(id=_uid(), article_id=art2.id, embedding=shared_emb)
    art2.analysis = ana2

    art3 = Article(
        id=_uid(),
        title="Researchers React to AI Startup's Reasoning Model",
        slug="researchers-react-reasoning-model",
        content="Researchers praise the mathematical reasoning capabilities.",
        status="PUBLISHED",
        published_at=_now() - timedelta(hours=2),
    )
    ana3 = ArticleAnalysis(id=_uid(), article_id=art3.id, embedding=shared_emb)
    art3.analysis = ana3

    art4 = Article(
        id=_uid(),
        title="AI Startup CEO Discusses Model Architecture and Safety",
        slug="ai-startup-ceo-discusses-model-architecture",
        content="The CEO addressed safety evaluations during an interview.",
        status="PUBLISHED",
        published_at=_now() - timedelta(hours=1),
    )
    ana4 = ArticleAnalysis(id=_uid(), article_id=art4.id, embedding=shared_emb)
    art4.analysis = ana4

    # Article 5: Unrelated competing model from different company
    art5 = Article(
        id=_uid(),
        title="Unrelated Robotics Startup Unveils Autonomous Warehouse Arm",
        slug="robotics-startup-warehouse-arm",
        content="A robotics firm unveiled an industrial warehouse logistics arm.",
        status="PUBLISHED",
        published_at=_now() - timedelta(minutes=30),
    )
    ana5 = ArticleAnalysis(id=_uid(), article_id=art5.id, embedding=unrelated_emb)
    art5.analysis = ana5

    db_session.add_all([art1, art2, art3, art4, art5, ana1, ana2, ana3, ana4, ana5])
    await db_session.commit()

    s1, _, is_n1 = await service.ingest_article_into_story(art1.id)
    await db_session.commit()
    assert is_n1 is True

    s2, _, is_n2 = await service.ingest_article_into_story(art2.id)
    await db_session.commit()
    assert is_n2 is False

    s3, _, is_n3 = await service.ingest_article_into_story(art3.id)
    await db_session.commit()
    assert is_n3 is False

    s4, _, is_n4 = await service.ingest_article_into_story(art4.id)
    await db_session.commit()
    assert is_n4 is False

    s5, _, is_n5 = await service.ingest_article_into_story(art5.id)
    await db_session.commit()
    assert is_n5 is True

    # Articles 1-4 must belong to the same story
    assert s1.id == s2.id == s3.id == s4.id
    assert s1.article_count == 4

    # Article 5 must belong to a different story
    assert s5.id != s1.id
    assert s5.article_count == 1


@pytest.mark.asyncio
async def test_story_search(db_session):
    """Test 22: Searching stories by full text query."""
    service = StoryIntelligenceService(db_session)

    art = Article(
        id=_uid(),
        title="Breakthrough Quantum Computing Demonstration",
        slug="quantum-computing-breakthrough",
        content="Physicists demonstrated quantum supremacy in error-corrected qubits.",
        status="PUBLISHED",
        published_at=_now(),
    )
    ana = ArticleAnalysis(id=_uid(), article_id=art.id, embedding=_vec(9))
    db_session.add_all([art, ana])
    await db_session.commit()

    await service.ingest_article_into_story(art.id)
    await db_session.commit()

    search_res = await service.search_stories("Quantum Computing")
    assert search_res.total >= 1
    assert any("Quantum" in s.title for s in search_res.results)


@pytest.mark.asyncio
async def test_batch_process_unassigned_articles(db_session):
    """Test 26: Background batch processing assigns unassigned articles to stories."""
    service = StoryIntelligenceService(db_session)
    art = Article(
        id=_uid(),
        title="Renewable Energy Hits 50% Generation Record",
        slug="renewable-energy-record-50",
        content="Clean energy accounted for over half of electricity generated.",
        status="PUBLISHED",
        published_at=_now(),
    )
    ana = ArticleAnalysis(id=_uid(), article_id=art.id, embedding=_vec(10))
    db_session.add_all([art, ana])
    await db_session.commit()

    assigned = await service.batch_process_unassigned_articles(limit=10)
    assert assigned >= 1

    # Verify article is now in a story
    stmt = select(StoryArticle).where(StoryArticle.article_id == art.id)
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_story_coverage_and_related_api(db_session):
    """Test 16 & Related: Story coverage grouping and related stories retrieval."""
    service = StoryIntelligenceService(db_session)

    topic = Topic(id=_uid(), name="Astronomy", slug="astronomy")
    db_session.add(topic)
    await db_session.commit()

    art1 = Article(
        id=_uid(),
        title="James Webb Space Telescope Discovers Early Galaxy",
        slug="jwst-discovers-early-galaxy-1",
        content="Astronomers identify redshift 14 galaxy.",
        status="PUBLISHED",
        published_at=_now() - timedelta(hours=3),
    )
    art1.topics = [topic]
    ana1 = ArticleAnalysis(id=_uid(), article_id=art1.id, embedding=_vec(11))
    art1.analysis = ana1

    art2 = Article(
        id=_uid(),
        title="Spectroscopic Analysis of JWST Early Galaxy",
        slug="jwst-galaxy-spectroscopy-2",
        content="Follow-up spectroscopy confirms stellar age.",
        status="PUBLISHED",
        published_at=_now() - timedelta(hours=1),
    )
    art2.topics = [topic]
    ana2 = ArticleAnalysis(id=_uid(), article_id=art2.id, embedding=_vec(11))
    art2.analysis = ana2

    db_session.add_all([art1, art2, ana1, ana2])
    await db_session.commit()

    story, _, _ = await service.ingest_article_into_story(art1.id)
    await db_session.commit()
    await service.ingest_article_into_story(art2.id)
    await db_session.commit()

    # Get coverage breakdown
    coverage = await service.get_story_coverage(str(story.id))
    assert coverage is not None
    assert coverage.total_articles == 2
    assert "PRIMARY" in coverage.articles_by_relationship

    # Get timeline
    timeline = await service.get_story_timeline(str(story.id))
    assert len(timeline) == 2

    # Get related stories
    related = await service.get_related_stories(str(story.id), limit=5)
    assert isinstance(related, list)

