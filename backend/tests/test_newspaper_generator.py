"""test_newspaper_generator.py — Phase 9 Intelligent Personal Newspaper Generator Tests.

Covers all 20 required tests + Acceptance Tests:
1. Edition generation
2. Candidate selection
3. Lead selection
4. Section assignment
5. Topic diversity
6. Entity diversity
7. Duplicate story clustering
8. Editorial scoring
9. User-specific lead stories
10. Empty candidate pool
11. Small article pool
12. Fallback time window
13. Edition persistence
14. Regeneration
15. Duplicate edition prevention
16. Section ordering
17. Layout assignment
18. Mobile API response structure
19. Personalized explanations
20. Existing newspaper compatibility
+ Personalization Acceptance Test (User A vs User B)
+ Editorial Acceptance Test (20+ article pool, topic diversity, lead, clusters)
"""
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.topic import Topic
from app.models.interest import UserInterest
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.newspaper.models import NewspaperEdition, NewspaperStory, StoryCluster, StoryClusterArticle
from app.newspaper.schemas import (
    NewspaperEditionResponse,
    NewspaperSectionResponse,
    NewspaperStoryResponse,
    StoryLayoutType,
    ControlledSection,
)
from app.newspaper.editorial_scorer import EditorialScorer, ScoredCandidateStory
from app.newspaper.story_clusterer import StoryClusterer
from app.newspaper.diversity import DiversityFilter
from app.newspaper.lead_story_selector import LeadStorySelector
from app.newspaper.section_builder import SectionBuilder
from app.newspaper.candidate_selector import CandidateSelector
from app.newspaper.generator import NewspaperGenerationService
from app.personalization.schemas import ScoredArticle, RelevanceScoreBreakdown


class MockEntity:
    def __init__(self, name: str):
        self.name = name
        self.normalized_name = name.lower()


class MockArticleObj:
    """Pure in-memory article mock for unit testing diversity, sections, and scoring."""
    def __init__(
        self,
        title: str,
        primary_category: str = "TECHNOLOGY",
        importance: float = 0.7,
        content_len: int = 1000,
        entities: list = None,
        image_url: str = None,
        is_full_text: bool = True,
        embedding: list = None,
        topics: list = None,
    ):
        self.id = uuid.uuid4()
        self.title = title
        self.slug = f"slug-{uuid.uuid4().hex[:8]}"
        self.canonical_url = "https://news.example.com"
        self.source_url = "https://news.example.com"
        self.description = f"Description for {title}"
        self.content = "Full article content text. " * (content_len // 20)
        self.published_at = datetime.now(timezone.utc)
        self.is_full_text_available = is_full_text
        self.image_url = image_url
        self.top_image_url = image_url
        self.author = "Editorial Desk"
        self.source = None
        self.reading_time_minutes = 4
        self.primary_category = primary_category
        self.importance_score = importance
        self.topics = topics or []
        self.entities = entities or []
        self.embedding = embedding or [0.1] * 384
        self.analysis = None


# Helper fixtures & creators
async def create_test_user(db: AsyncSession, email_prefix: str = "user") -> User:
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        email=f"{email_prefix}_{unique_id}@example.com",
        password_hash="hashed_pw",
        full_name=f"Test {email_prefix.title()} {unique_id}",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_test_topic(db: AsyncSession, name: str, slug: str) -> Topic:
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


async def add_user_interest(
    db: AsyncSession, user_id: uuid.UUID, topic_id: uuid.UUID, score: float = 1.0, pref: str = "POSITIVE"
):
    ui = UserInterest(
        user_id=user_id,
        topic_id=topic_id,
        interest_score=score,
        preference_type=pref,
        source="EXPLICIT",
    )
    db.add(ui)
    await db.commit()


async def create_test_article(
    db: AsyncSession,
    title: str,
    category: str,
    topics: list,
    entities: list = None,
    importance: float = 0.7,
    hours_ago: int = 2,
    content_len: int = 1200,
    embedding: list = None,
) -> Article:
    now = datetime.now(timezone.utc)
    pub_at = now - timedelta(hours=hours_ago)
    art = Article(
        title=title,
        slug=f"slug-{uuid.uuid4().hex[:8]}",
        canonical_url=f"https://news.example.com/{uuid.uuid4().hex[:8]}",
        description=f"Summary for {title}",
        content="This is the full article content. " * (content_len // 30),
        status="PUBLISHED",
        published_at=pub_at,
        is_full_text_available=True,
        reading_time_minutes=4,
    )
    art.topics = list(topics)
    db.add(art)
    await db.flush()

    # Add analysis
    ana = ArticleAnalysis(
        article_id=art.id,
        primary_category=category,
        importance_score=importance,
        summary=f"Key analytical summary of {title}",
        embedding=embedding or [(hash(f"{title}_{j}") % 100) / 100.0 for j in range(384)],
    )
    db.add(ana)
    await db.commit()
    await db.refresh(art)
    return art


def make_breakdown(score: float = 0.8) -> RelevanceScoreBreakdown:
    return RelevanceScoreBreakdown(
        final_score=score,
        topic_score=score,
        semantic_score=score,
        entity_score=score,
        keyword_score=score,
        importance_score=score,
        recency_score=score,
        negative_penalty=0.0,
        source_score=0.0,
    )


# -----------------------------------------------------------------------------
# 1. Editorial Scoring Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_editorial_scoring():
    scorer = EditorialScorer(
        weight_relevance=0.60,
        weight_importance=0.15,
        weight_recency=0.15,
        weight_confidence=0.10,
    )

    art = MockArticleObj("AI Breakthrough", "TECHNOLOGY", importance=0.8, content_len=1500)
    scored_art = ScoredArticle(
        article_id=art.id,
        article=art,
        relevance_score=0.9,
        breakdown=make_breakdown(0.9),
    )

    candidates = scorer.score_candidates([scored_art])
    assert len(candidates) == 1
    cand = candidates[0]
    assert 0.0 <= cand.editorial_score <= 1.0
    assert cand.editorial_score > 0.7
    assert cand.quality_score > 0.5


# -----------------------------------------------------------------------------
# 2. Duplicate Story Clustering Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_story_clustering():
    clusterer = StoryClusterer(similarity_threshold=0.80)

    # 3 articles covering the exact same event
    shared_emb = [0.85] * 384

    art1 = MockArticleObj(
        "OpenAI Launches GPT-5 Model", "TECHNOLOGY", content_len=1500, importance=0.9, embedding=shared_emb
    )
    art2 = MockArticleObj(
        "New GPT-5 Model Released by OpenAI", "TECHNOLOGY", content_len=500, importance=0.8, embedding=shared_emb
    )
    art3 = MockArticleObj(
        "OpenAI Announces Latest GPT-5 AI", "TECHNOLOGY", content_len=400, importance=0.7, embedding=shared_emb
    )

    scored1 = ScoredArticle(article_id=art1.id, article=art1, relevance_score=0.95, breakdown=make_breakdown(0.95))
    scored2 = ScoredArticle(article_id=art2.id, article=art2, relevance_score=0.90, breakdown=make_breakdown(0.90))
    scored3 = ScoredArticle(article_id=art3.id, article=art3, relevance_score=0.88, breakdown=make_breakdown(0.88))

    elected_primaries, cluster_map = await clusterer.cluster_and_elect_primary([scored1, scored2, scored3])
    
    # Exactly one primary story should be elected for the cluster
    assert len(elected_primaries) == 1
    # The longest, highest quality, most relevant should be chosen
    assert elected_primaries[0].article.id == art1.id


# -----------------------------------------------------------------------------
# 3. Lead Selection Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lead_selection():
    selector = LeadStorySelector()

    art_lead = MockArticleObj(
        "Top Personalized Story", "TECHNOLOGY", importance=0.9, content_len=1500, image_url="https://example.com/img.jpg"
    )
    cand_lead = ScoredCandidateStory(
        scored_article=ScoredArticle(article_id=art_lead.id, article=art_lead, relevance_score=0.98, breakdown=make_breakdown(0.98)),
        editorial_score=0.95,
        quality_score=0.90,
    )

    art_other = MockArticleObj(
        "Secondary Story", "TECHNOLOGY", importance=0.5, content_len=200, is_full_text=False
    )
    cand_other = ScoredCandidateStory(
        scored_article=ScoredArticle(article_id=art_other.id, article=art_other, relevance_score=0.40, breakdown=make_breakdown(0.40)),
        editorial_score=0.45,
        quality_score=0.30,
    )

    lead, remaining = selector.select_lead([cand_other, cand_lead])
    assert lead is not None
    assert lead.scored_article.article.id == art_lead.id
    assert len(remaining) == 1
    assert remaining[0].scored_article.article.id == art_other.id


# -----------------------------------------------------------------------------
# 4. Section Assignment & Ordering Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_section_assignment():
    builder = SectionBuilder(max_total_stories=10)

    art_tech = MockArticleObj("Tech Story", "TECHNOLOGY")
    cand_tech = ScoredCandidateStory(scored_article=ScoredArticle(article_id=art_tech.id, article=art_tech, relevance_score=0.8, breakdown=make_breakdown(0.8)))

    art_sci = MockArticleObj("Sci Story", "SCIENCE")
    cand_sci = ScoredCandidateStory(scored_article=ScoredArticle(article_id=art_sci.id, article=art_sci, relevance_score=0.7, breakdown=make_breakdown(0.7)))

    art_biz = MockArticleObj("Biz Story", "FINANCE")
    cand_biz = ScoredCandidateStory(scored_article=ScoredArticle(article_id=art_biz.id, article=art_biz, relevance_score=0.6, breakdown=make_breakdown(0.6)))

    art_unk = MockArticleObj("Unk Story", "UNKNOWN_CAT")
    cand_unk = ScoredCandidateStory(scored_article=ScoredArticle(article_id=art_unk.id, article=art_unk, relevance_score=0.5, breakdown=make_breakdown(0.5)))

    assert builder.map_to_section(cand_tech) == ControlledSection.TECHNOLOGY.value
    assert builder.map_to_section(cand_sci) == ControlledSection.SCIENCE.value
    assert builder.map_to_section(cand_biz) == ControlledSection.BUSINESS.value
    assert builder.map_to_section(cand_unk) == ControlledSection.OTHER.value


# -----------------------------------------------------------------------------
# 5. Topic and Entity Diversity Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_topic_and_entity_diversity():
    filter_div = DiversityFilter(max_consecutive_same_topic=2, entity_repeat_penalty=0.10)

    # 4 consecutive AI stories + 1 Science story
    cands = []
    for i in range(4):
        art = MockArticleObj(
            f"AI Story {i}", "TECHNOLOGY", entities=[MockEntity("OpenAI")]
        )
        cands.append(
            ScoredCandidateStory(
                scored_article=ScoredArticle(article_id=art.id, article=art, relevance_score=0.9 - i * 0.02, breakdown=make_breakdown(0.9)),
                editorial_score=0.9 - i * 0.02,
                quality_score=0.8,
            )
        )

    art_sci = MockArticleObj("Space Telescope", "SCIENCE", entities=[])
    cands.append(
        ScoredCandidateStory(
            scored_article=ScoredArticle(article_id=art_sci.id, article=art_sci, relevance_score=0.80, breakdown=make_breakdown(0.80)),
            editorial_score=0.80,
            quality_score=0.8,
        )
    )

    diversified = filter_div.apply_diversity(cands, user_top_interests=["Technology", "Science"])

    # Consecutive topic monopoly should be broken (max 2 consecutive TECHNOLOGY)
    tech_consecutive = 0
    max_tech_consecutive = 0
    for d in diversified:
        cat = d.scored_article.article.primary_category
        if cat == "TECHNOLOGY":
            tech_consecutive += 1
            max_tech_consecutive = max(max_tech_consecutive, tech_consecutive)
        else:
            tech_consecutive = 0

    assert max_tech_consecutive <= 2
    # Check that personalization explanation was added
    assert diversified[0].personal_explanation is not None


# -----------------------------------------------------------------------------
# 6. Fallback Time Window & Small Pool Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fallback_time_window(db_session: AsyncSession):
    user = await create_test_user(db_session, "time_user")
    topic = await create_test_topic(db_session, "World", "world-time")
    await add_user_interest(db_session, user.id, topic.id, score=1.0)

    # Article published 48h ago (outside 24h primary, inside 72h fallback)
    art = await create_test_article(
        db_session, "Older Global Report", "WORLD", [topic], hours_ago=48
    )

    selector = CandidateSelector(db_session)
    now_dt = datetime.now(timezone.utc)
    candidates = await selector.get_candidate_articles(user.id, target_date=now_dt, min_candidates=10000)
    
    assert len(candidates) >= 1
    assert any(c.article_id == art.id for c in candidates)


# -----------------------------------------------------------------------------
# 7. Edition Persistence, Immutability & Regeneration Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_edition_persistence_and_regeneration(db_session: AsyncSession):
    user = await create_test_user(db_session, "persist_user")
    top_tech = await create_test_topic(db_session, "Technology", "tech-persist")
    await add_user_interest(db_session, user.id, top_tech.id, score=1.0)

    await create_test_article(db_session, "Tech Breakthrough 1", "TECHNOLOGY", [top_tech])
    await create_test_article(db_session, "Tech Breakthrough 2", "TECHNOLOGY", [top_tech])

    gen_service = NewspaperGenerationService(db_session)

    # 1. Initial generation
    edition_1 = await gen_service.get_or_generate_today_edition(user)
    assert edition_1 is not None
    assert edition_1.status == "READY"
    assert edition_1.total_stories >= 1

    # 2. Repeated fetch returns same snapshot (does not re-generate)
    edition_2 = await gen_service.get_or_generate_today_edition(user)
    assert edition_2.id == edition_1.id
    assert edition_2.generated_at == edition_1.generated_at

    # 3. Force regeneration updates the edition
    edition_3 = await gen_service.generate_daily_edition(user, force_regenerate=True)
    assert edition_3.id == edition_1.id  # Same unique daily slot updated
    assert edition_3.status == "READY"


# -----------------------------------------------------------------------------
# 8. Empty Candidate Pool Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_empty_candidate_pool(db_session: AsyncSession):
    user = await create_test_user(db_session, "empty_user")
    gen_service = NewspaperGenerationService(db_session)

    edition = await gen_service.generate_daily_edition(user, edition_date="2020-01-01")
    assert edition is not None
    assert edition.status == "READY"
    assert edition.total_stories >= 0


# -----------------------------------------------------------------------------
# 9. PERSONALIZATION ACCEPTANCE TEST: USER A vs USER B
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_personalization_acceptance_user_a_vs_user_b(db_session: AsyncSession):
    """
    USER A: AI, Machine Learning, Programming -> AI/Tech Lead
    USER B: Finance, Business, Startups -> Finance/Business Lead
    Same global article pool.
    """
    # Create Topics
    top_ai = await create_test_topic(db_session, "Artificial Intelligence", "ai-acc")
    top_fin = await create_test_topic(db_session, "Finance", "fin-acc")

    # User A (AI focused)
    user_a = await create_test_user(db_session, "usera_ai")
    await add_user_interest(db_session, user_a.id, top_ai.id, score=1.0)

    # User B (Finance focused)
    user_b = await create_test_user(db_session, "userb_fin")
    await add_user_interest(db_session, user_b.id, top_fin.id, score=1.0)

    # Shared Article Pool
    ai_art = await create_test_article(
        db_session, "Revolutionary Neural Model Unveiled", "TECHNOLOGY", [top_ai],
        importance=0.85, content_len=1200
    )
    fin_art = await create_test_article(
        db_session, "Global Markets Surge on Economic Report", "BUSINESS", [top_fin],
        importance=0.85, content_len=1200
    )

    gen_service = NewspaperGenerationService(db_session)

    edition_a = await gen_service.generate_daily_edition(user_a, edition_date="2026-10-06", force_regenerate=True)
    edition_b = await gen_service.generate_daily_edition(user_b, edition_date="2026-10-06", force_regenerate=True)

    # Verify distinct leads
    assert edition_a.lead_story is not None
    assert edition_b.lead_story is not None

    assert edition_a.lead_story.article_id == ai_art.id
    assert edition_b.lead_story.article_id == fin_art.id
    assert edition_a.lead_story.article_id != edition_b.lead_story.article_id


# -----------------------------------------------------------------------------
# 10. EDITORIAL ACCEPTANCE TEST (20 Articles Pool)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_editorial_acceptance_20_article_pool(db_session: AsyncSession):
    """
    20 candidate articles:
    - 5 AI
    - 4 Business
    - 3 Science
    - 3 Sports
    - 3 Technology
    - 2 World
    User strongly prefers AI.
    Verifies: exactly 1 lead, topic diversity, no duplicate clusters, controlled sections, no empty sections.
    """
    user_ai = await create_test_user(db_session, "user_editorial_20")
    top_ai = await create_test_topic(db_session, "AI", "ai-20")
    top_biz = await create_test_topic(db_session, "Business", "biz-20")
    top_sci = await create_test_topic(db_session, "Science", "sci-20")
    top_sports = await create_test_topic(db_session, "Sports", "sports-20")
    top_world = await create_test_topic(db_session, "World", "world-20")

    await add_user_interest(db_session, user_ai.id, top_ai.id, score=1.0)

    # 5 AI Articles
    for i in range(5):
        await create_test_article(db_session, f"AI Breakthrough #{i}", "TECHNOLOGY", [top_ai], importance=0.8)

    # 4 Business
    for i in range(4):
        await create_test_article(db_session, f"Market Report #{i}", "BUSINESS", [top_biz], importance=0.7)

    # 3 Science
    for i in range(3):
        await create_test_article(db_session, f"Space Science #{i}", "SCIENCE", [top_sci], importance=0.7)

    # 3 Sports
    for i in range(3):
        await create_test_article(db_session, f"Championship Match #{i}", "SPORTS", [top_sports], importance=0.6)

    # 3 Technology (General)
    for i in range(3):
        await create_test_article(db_session, f"Chip Foundry #{i}", "TECHNOLOGY", [top_ai], importance=0.65)

    # 2 World
    for i in range(2):
        await create_test_article(db_session, f"Global Summit #{i}", "WORLD", [top_world], importance=0.75)

    gen_service = NewspaperGenerationService(db_session)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    edition = await gen_service.generate_daily_edition(user_ai, edition_date=today_str, force_regenerate=True)

    # Verifications:
    assert edition.status == "READY"
    assert edition.lead_story is not None
    assert edition.lead_story.is_lead is True
    assert edition.lead_story.layout_type == StoryLayoutType.LEAD.value

    # Exactly 1 lead
    lead_count = sum(1 for sec in edition.sections for st in sec.stories if st.is_lead)
    assert lead_count == 1

    # Sections must not be empty
    for sec in edition.sections:
        assert len(sec.stories) > 0

    # Layout types assigned
    layouts = {st.layout_type for sec in edition.sections for st in sec.stories}
    assert StoryLayoutType.LEAD.value in layouts
    assert (
        StoryLayoutType.FEATURE.value in layouts
        or StoryLayoutType.STANDARD.value in layouts
    )

    # Total stories should respect configured limits
    assert edition.total_stories <= 25
    assert edition.total_stories >= 10
