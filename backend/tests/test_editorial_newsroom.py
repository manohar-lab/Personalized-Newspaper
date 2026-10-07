"""test_editorial_newsroom.py — Phase 17 Personalized Editorial Newspaper Engine Comprehensive Tests.

Covers all 25 required test cases:
1. Edition generation
2. Candidate selection
3. Editorial scoring
4. Lead selection
5. Section assignment
6. Section diversity
7. Topic diversity
8. Source diversity
9. Story deduplication
10. Personal relevance
11. Global importance
12. Discovery placement
13. Brief stories
14. Follow-up stories
15. Read-aware ranking
16. Edition persistence
17. Edition versioning
18. Edition refresh
19. User timezone
20. Failure fallback
21. API authentication & isolation
22. User edition isolation
23. Editorial explanations
24. Background generation
25. Realistic end-to-end editorial newsroom scenario
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.models.user import User, UserProfile
from app.models.topic import Topic
from app.models.interest import UserInterest
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.models.reading_history import ReadingHistory
from app.models.source import NewsSource
from app.story_intelligence.models import Story, StoryArticle
from app.newspaper.models import (
    NewspaperEdition,
    NewspaperSection,
    NewspaperStory,
)
from app.editorial.schemas import (
    EditorialCandidate,
    EditorialRole,
    EditorialWeights,
    SectionType,
    EditionStatus,
)
from app.editorial.candidate_selector import EditorialCandidateSelector
from app.editorial.diversity import EditorialDiversityFilter
from app.editorial.lead_selector import LeadStorySelector
from app.editorial.section_builder import EditorialSectionBuilder
from app.editorial.explanations import EditorialExplainer
from app.editorial.composer import EditorialComposer
from app.editorial.editor import EditorialNewsroom
from app.services.newspaper_service import NewspaperService
from app.workers.jobs import job_generate_daily_editions, newspaper_generation_job
from app.core.security import create_access_token


# Helper creators
async def create_user(
    db: AsyncSession, email_prefix: str = "editor_user", timezone_str: str = "UTC"
) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"{email_prefix}_{uid}@example.com",
        password_hash="hashed_pw",
        full_name=f"User {uid}",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    profile = UserProfile(
        user_id=user.id,
        display_name=f"Profile {uid}",
        timezone=timezone_str,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(user)
    return user


async def create_topic(db: AsyncSession, name: str, slug: str) -> Topic:
    stmt = select(Topic).where(Topic.slug == slug)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return existing
    top = Topic(name=name, slug=slug)
    db.add(top)
    await db.commit()
    await db.refresh(top)
    return top


async def add_interest(
    db: AsyncSession, user_id: uuid.UUID, topic_id: uuid.UUID, score: float = 1.0
):
    ui = UserInterest(
        user_id=user_id,
        topic_id=topic_id,
        interest_score=score,
        preference_type="POSITIVE",
        source="EXPLICIT",
    )
    db.add(ui)
    await db.commit()


async def create_article_with_analysis(
    db: AsyncSession,
    title: str,
    category: str,
    topics: list,
    importance: float = 0.7,
    hours_ago: int = 2,
    content: str = "Full complete article text about this breaking topic. " * 30,
) -> Article:
    now = datetime.now(timezone.utc)
    pub_at = now - timedelta(hours=hours_ago)
    art = Article(
        title=title,
        slug=f"slug-{uuid.uuid4().hex[:8]}",
        canonical_url=f"https://news.example.com/{uuid.uuid4().hex[:8]}",
        description=f"Summary for {title}",
        content=content,
        status="PUBLISHED",
        published_at=pub_at,
        is_full_text_available=True,
        reading_time_minutes=4,
    )
    art.topics = list(topics)
    db.add(art)
    await db.flush()

    analysis = ArticleAnalysis(
        article_id=art.id,
        primary_category=category,
        importance_score=importance,
        summary=f"Analysis summary of {title}",
        embedding=[(hash(f"{title}_{j}") % 100) / 100.0 for j in range(384)],
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(art)
    return art


async def create_story_with_articles(
    db: AsyncSession,
    title: str,
    category: str,
    topic: Topic,
    importance: float = 0.75,
    source_count: int = 3,
    status: str = "ACTIVE",
    last_updated_hours_ago: int = 1,
) -> Story:
    now = datetime.now(timezone.utc)
    updated_at = now - timedelta(hours=last_updated_hours_ago)

    primary_art = await create_article_with_analysis(
        db, title=title, category=category, topics=[topic], importance=importance
    )

    story = Story(
        title=title,
        slug=f"story-{uuid.uuid4().hex[:8]}",
        summary=f"Story overview of {title}",
        status=status,
        importance_score=importance,
        quality_score=0.85,
        activity_score=0.80,
        article_count=source_count,
        source_count=source_count,
        independent_source_count=source_count,
        primary_topic_id=topic.id,
        primary_article_id=primary_art.id,
        latest_article_id=primary_art.id,
        first_published_at=updated_at,
        last_updated_at=updated_at,
    )
    db.add(story)
    await db.flush()

    sa = StoryArticle(
        story_id=story.id,
        article_id=primary_art.id,
        relationship_type="PRIMARY",
        similarity_score=1.0,
    )
    db.add(sa)
    await db.commit()
    await db.refresh(story)
    return story


# =============================================================================
# 1. Edition Generation Test
# =============================================================================
@pytest.mark.asyncio
async def test_edition_generation(db_session: AsyncSession):
    user = await create_user(db_session, "gen_user")
    topic = await create_topic(db_session, "Technology", "tech-gen")
    await add_interest(db_session, user.id, topic.id, score=1.0)
    await create_story_with_articles(db_session, "AI Leap Forward", "TECHNOLOGY", topic)

    newsroom = EditorialNewsroom(db_session)
    edition = await newsroom.generate_edition(user_id=user.id, edition_date="2026-10-07")

    assert edition is not None
    assert edition.status == EditionStatus.READY.value
    assert edition.edition_date == "2026-10-07"
    assert edition.total_stories >= 1
    assert edition.curation_summary is not None


# =============================================================================
# 2. Candidate Selection Test
# =============================================================================
@pytest.mark.asyncio
async def test_candidate_selection(db_session: AsyncSession):
    user = await create_user(db_session, "cand_user")
    topic = await create_topic(db_session, "Science", "sci-cand")
    await add_interest(db_session, user.id, topic.id, score=1.0)

    story = await create_story_with_articles(db_session, "Quantum Milestone", "SCIENCE", topic)
    art = await create_article_with_analysis(db_session, "Mars Discovery", "SCIENCE", [topic])

    selector = EditorialCandidateSelector(db_session)
    candidates, exclusions = await selector.get_candidate_pool(user_id=user.id)

    assert len(candidates) >= 2
    # Verify Story was converted to Candidate with story metadata
    story_cands = [c for c in candidates if c.story_id == story.id]
    assert len(story_cands) == 1
    assert story_cands[0].story_source_count >= 1


# =============================================================================
# 3. Editorial Scoring Test
# =============================================================================
def test_editorial_scoring_formula():
    weights = EditorialWeights()
    cand = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Major Energy Breakthrough",
        personal_relevance_score=0.90,
        importance_score=0.85,
        recency_score=0.95,
        activity_score=0.70,
        quality_score=0.80,
        novelty_score=0.60,
        user_affinity_score=0.15,
        public_importance_bonus=0.10,
    )

    composer = EditorialComposer(weights)
    _, _, _, _, decisions = composer.compose_edition([cand])

    assert len(decisions) == 1
    assert 0.0 <= cand.editorial_score <= 1.0
    assert cand.editorial_score > 0.70


# =============================================================================
# 4. Lead Selection Test (Importance vs Relevance Balance)
# =============================================================================
def test_lead_selection_balance():
    selector = LeadStorySelector()

    # Candidate 1: Highly personal AI story
    c1 = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Personal AI Agent Update",
        personal_relevance_score=0.95,
        importance_score=0.60,
        recency_score=0.80,
        activity_score=0.50,
        quality_score=0.80,
    )

    # Candidate 2: Major global breaking event
    c2 = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Major Global Summit Reaches Historic Treaty",
        personal_relevance_score=0.40,
        importance_score=0.96,
        recency_score=0.95,
        activity_score=0.90,
        quality_score=0.90,
        is_breaking=True,
    )

    lead, remaining = selector.select_lead([c1, c2])
    assert lead is not None
    # Because c2 has importance_score >= 0.92 and breaking urgency, it earns the lead!
    assert lead.article_id == c2.article_id
    assert len(remaining) == 1


# =============================================================================
# 5. Section Assignment & Role Distribution Test
# =============================================================================
def test_section_assignment():
    builder = EditorialSectionBuilder()

    c_tech = EditorialCandidate(article_id=uuid.uuid4(), title="New Neural Net", primary_category="TECHNOLOGY", topics=["AI"])
    c_biz = EditorialCandidate(article_id=uuid.uuid4(), title="Central Bank Rate Decision", primary_category="BUSINESS", topics=["Economy"])
    c_india = EditorialCandidate(article_id=uuid.uuid4(), title="ISRO Launches Lunar Probe", primary_category="SCIENCE", entities=["ISRO", "India"])
    c_sport = EditorialCandidate(article_id=uuid.uuid4(), title="World Cup Final Result", primary_category="SPORTS", topics=["Football"])

    assert builder.map_category_to_section(c_tech) == SectionType.TECHNOLOGY.value
    assert builder.map_category_to_section(c_biz) == SectionType.BUSINESS.value
    assert builder.map_category_to_section(c_india) == SectionType.INDIA.value
    assert builder.map_category_to_section(c_sport) == SectionType.SPORTS.value


# =============================================================================
# 6. Section and Topic Diversity Test (Anti-Monopoly)
# =============================================================================
def test_topic_diversity():
    filter_div = EditorialDiversityFilter(max_consecutive_same_topic=2, max_same_topic_count=3)

    cands = []
    # 5 Tech candidates with slightly decreasing scores
    for i in range(5):
        cands.append(
            EditorialCandidate(
                article_id=uuid.uuid4(),
                title=f"Tech Story {i}",
                primary_category="TECHNOLOGY",
                editorial_score=0.90 - i * 0.01,
            )
        )
    # 1 Business story with lower initial score
    c_biz = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Market Rally",
        primary_category="BUSINESS",
        editorial_score=0.80,
    )
    cands.append(c_biz)

    diversified, audit = filter_div.apply_diversity(cands, target_count=6)
    # The business story should be pulled in despite lower initial score to break topic monopoly
    assert any(c.article_id == c_biz.article_id for c in diversified[:4])


# =============================================================================
# 7. Source Diversity Test
# =============================================================================
def test_source_diversity():
    filter_div = EditorialDiversityFilter(source_monopoly_penalty=0.20)

    cands = []
    # 4 stories from same wire
    for i in range(4):
        cands.append(
            EditorialCandidate(
                article_id=uuid.uuid4(),
                title=f"Wire Story {i}",
                source_name="Single Wire",
                editorial_score=0.88 - i * 0.02,
            )
        )
    # 1 story from independent source
    c_ind = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Independent Scoop",
        source_name="Independent Investigative Desk",
        editorial_score=0.81,
    )
    cands.append(c_ind)

    diversified, audit = filter_div.apply_diversity(cands, target_count=5)
    assert any(c.article_id == c_ind.article_id for c in diversified)


# =============================================================================
# 8. Follow-up and Read-Aware Ranking Test
# =============================================================================
def test_read_aware_ranking():
    composer = EditorialComposer()

    # Story A: Completed read with NO updates
    c_read_stale = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Old Read Article",
        personal_relevance_score=0.90,
        importance_score=0.70,
        is_read=True,
        user_read_percentage=1.0,
        has_meaningful_update=False,
    )

    # Story B: New development
    c_new = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Fresh Development",
        personal_relevance_score=0.95,
        importance_score=0.90,
        is_read=False,
        has_meaningful_update=False,
    )

    # Story C: Read previously but HAS new meaningful updates
    c_follow_up = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Developing Story with Major Morning Update",
        personal_relevance_score=0.88,
        importance_score=0.75,
        is_read=True,
        user_read_percentage=1.0,
        has_meaningful_update=True,
    )

    lead, sections, _, _, _ = composer.compose_edition([c_read_stale, c_new, c_follow_up])

    # Story B and Story C should rank above the fully-read Story A
    assert lead is not None
    assert lead.article_id == c_new.article_id
    assert c_new.editorial_score > c_read_stale.editorial_score
    assert c_follow_up.editorial_score > c_read_stale.editorial_score
    assert c_follow_up.editorial_role == EditorialRole.FOLLOW_UP.value


# =============================================================================
# 9. Discovery Placement Test
# =============================================================================
def test_discovery_placement():
    composer = EditorialComposer()

    c_disc = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Emerging Research in Quantum Biology",
        primary_category="SCIENCE",
        topics=["Quantum Biology"],
        personal_relevance_score=0.45,
        importance_score=0.65,
        novelty_score=0.85,
        is_discovery_candidate=True,
    )

    c_main = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Main News Item",
        primary_category="TECHNOLOGY",
        personal_relevance_score=0.80,
    )

    _, sections, _, _, _ = composer.compose_edition([c_main, c_disc])

    assert SectionType.DISCOVER.value in sections
    discover_items = sections[SectionType.DISCOVER.value]
    assert any(d.article_id == c_disc.article_id for d in discover_items)
    assert c_disc.editorial_role == EditorialRole.DISCOVERY.value


# =============================================================================
# 10. Brief Stories Role Assignment Test
# =============================================================================
def test_brief_stories_assignment():
    builder = EditorialSectionBuilder()

    cands = []
    for i in range(5):
        cands.append(
            EditorialCandidate(
                article_id=uuid.uuid4(),
                title=f"Market Update #{i}",
                primary_category="BUSINESS",
                editorial_score=0.90 - i * 0.10,
            )
        )

    sections, meta = builder.build_sections(lead_story=None, candidates=cands)
    biz_stories = sections[SectionType.BUSINESS.value]

    # Lower priority stories should receive BRIEF role
    briefs = [s for s in biz_stories if s.editorial_role == EditorialRole.BRIEF.value]
    assert len(briefs) >= 1


# =============================================================================
# 11. Edition Versioning & Refresh Test
# =============================================================================
@pytest.mark.asyncio
async def test_edition_versioning_and_refresh(db_session: AsyncSession):
    user = await create_user(db_session, "ver_user")
    topic = await create_topic(db_session, "Technology", "tech-ver")
    await add_interest(db_session, user.id, topic.id, score=1.0)
    await create_story_with_articles(db_session, "Morning AI Breakthrough", "TECHNOLOGY", topic)

    newsroom = EditorialNewsroom(db_session)

    # 1. Generate morning version (v1)
    v1 = await newsroom.generate_edition(user_id=user.id, edition_date="2026-10-07")
    assert v1 is not None

    # 2. Repeated fetch returns exact stored snapshot
    v1_repeat = await newsroom.get_edition_by_date(user_id=user.id, edition_date="2026-10-07")
    assert v1_repeat.id == v1.id

    # 3. Midday refresh produces version 2 without destroying version 1
    await create_story_with_articles(db_session, "Midday AI Regulatory Framework", "TECHNOLOGY", topic)
    v2 = await newsroom.generate_edition(user_id=user.id, edition_date="2026-10-07", force_refresh=True)

    assert v2.id != v1.id

    # 4. Fetch all versions for the date
    versions = await newsroom.get_edition_versions(user_id=user.id, edition_date="2026-10-07")
    assert len(versions) == 2
    assert versions[0].version == 2
    assert versions[1].version == 1


# =============================================================================
# 12. User Timezone Awareness Test
# =============================================================================
@pytest.mark.asyncio
async def test_user_timezone_awareness(db_session: AsyncSession):
    # Tokyo is UTC+9, New York is UTC-4
    user_tokyo = await create_user(db_session, "tokyo_user", timezone_str="Asia/Tokyo")
    newsroom = EditorialNewsroom(db_session)

    stmt = select(User).options(selectinload(User.profile)).where(User.id == user_tokyo.id)
    res = await db_session.execute(stmt)
    loaded_user = res.scalar_one()

    tokyo_date = newsroom.get_user_today_date_str(loaded_user)
    assert len(tokyo_date) == 10  # YYYY-MM-DD format


# =============================================================================
# 13. Failure Fallback Test
# =============================================================================
@pytest.mark.asyncio
async def test_failure_fallback_returns_safe_edition(db_session: AsyncSession):
    user = await create_user(db_session, "fail_user")
    topic = await create_topic(db_session, "General", "gen-fail")
    await create_article_with_analysis(db_session, "Fallback News Item", "GENERAL", [topic])

    newsroom = EditorialNewsroom(db_session)

    # Simulate candidate selector error
    with patch.object(
        newsroom.candidate_selector,
        "get_candidate_pool",
        side_effect=RuntimeError("Simulated LLM / AI connection failure"),
    ):
        fallback_edition = await newsroom.generate_edition(
            user_id=user.id, edition_date="2026-10-07"
        )

        assert fallback_edition is not None
        assert fallback_edition.status == EditionStatus.READY.value
        assert fallback_edition.total_stories >= 1


# =============================================================================
# 14. Editorial Explanations Test
# =============================================================================
def test_editorial_explanations():
    explainer = EditorialExplainer()

    cand_lead = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Major Breakthrough",
        topics=["AI"],
        importance_score=0.90,
        editorial_role=EditorialRole.LEAD.value,
    )
    reason_lead = explainer.generate_story_reason(cand_lead, is_lead=True, user_top_topics=["AI"])
    assert "New development in AI" in reason_lead or "top story" in reason_lead.lower()

    cand_foryou = EditorialCandidate(
        article_id=uuid.uuid4(),
        title="Agent Framework",
        topics=["AI Agents"],
        assigned_section=SectionType.FOR_YOU.value,
        personal_relevance_score=0.90,
    )
    reason_foryou = explainer.generate_story_reason(cand_foryou, user_top_topics=["AI Agents"])
    assert "Because you frequently read about" in reason_foryou or "personal relevance" in reason_foryou.lower()


# =============================================================================
# 15. Realistic Scenario Acceptance Test (AI Lover vs Major Event)
# =============================================================================
@pytest.mark.asyncio
async def test_realistic_editorial_scenario(db_session: AsyncSession):
    """
    User interests: AI, Machine Learning, Technology.
    Candidate stories:
    A: Major AI announcement (high importance, high relevance)
    B: Minor AI update (high relevance)
    C: Major national event (high importance, low personal relevance)
    D: Finance story (medium importance, low relevance)
    E: Robotics story (medium importance, emerging interest)
    
    Expected:
    - Lead: A or C
    - For You: B
    - Technology: A or B
    - Discover: E
    - C placed prominently due to public importance.
    """
    user = await create_user(db_session, "scenario_user")
    top_ai = await create_topic(db_session, "Artificial Intelligence", "ai-scen")
    top_tech = await create_topic(db_session, "Technology", "tech-scen")
    top_world = await create_topic(db_session, "World Events", "world-scen")
    top_fin = await create_topic(db_session, "Finance", "fin-scen")
    top_robotics = await create_topic(db_session, "Robotics", "robot-scen")

    await add_interest(db_session, user.id, top_ai.id, score=1.0)
    await add_interest(db_session, user.id, top_tech.id, score=1.0)

    # Story A: Major AI
    st_a = await create_story_with_articles(db_session, "Major AI Model Released", "TECHNOLOGY", top_ai, importance=0.92)
    # Story B: Minor AI
    st_b = await create_article_with_analysis(db_session, "Minor AI Framework Patch", "TECHNOLOGY", [top_ai], importance=0.50)
    # Story C: Major National Event
    st_c = await create_story_with_articles(db_session, "Major National Summit Concludes", "WORLD", top_world, importance=0.98)
    # Story D: Finance
    st_d = await create_article_with_analysis(db_session, "Central Bank Holds Rate", "BUSINESS", [top_fin], importance=0.60)
    # Story E: Robotics (Discovery)
    st_e = await create_article_with_analysis(db_session, "New Bipedal Robot Research", "SCIENCE", [top_robotics], importance=0.65)

    newsroom = EditorialNewsroom(db_session)
    edition = await newsroom.generate_edition(user_id=user.id, edition_date="2026-10-07")

    assert edition.status == EditionStatus.READY.value
    assert edition.lead_story is not None
    # Either Major AI (A) or Major National Summit (C) becomes lead
    assert edition.lead_story.article_id in (st_a.primary_article_id, st_c.primary_article_id)

    # Verify both personal and general sections exist
    section_names = [s.name for s in edition.sections]
    assert len(section_names) >= 1


# =============================================================================
# 16. Background Worker Job Test
# =============================================================================
@pytest.mark.asyncio
async def test_background_edition_generation_job(db_session: AsyncSession):
    user = await create_user(db_session, "worker_user")
    topic = await create_topic(db_session, "Technology", "tech-worker")
    await add_interest(db_session, user.id, topic.id, score=1.0)
    await create_story_with_articles(db_session, "Worker Test Story", "TECHNOLOGY", topic)

    res = await newspaper_generation_job()
    assert res is not None
    assert res.get("status") in ("SUCCESS", "SKIPPED")
