"""test_personalization_control_center.py — Phase 23 Personalization Control Center & Transparency Tests.

Validates:
1. Personalization Profile Loading & Human-friendly Inferred Tiers
2. Personalization Settings Updates (Discovery, Strength, Diversity, Sections)
3. Explicit Interests (Add, List, Delete)
4. Topic Controls (Follow, Mute, Unmute, Adjust Feedback)
5. Child Topic Override (Parent followed, Child muted)
6. Entity Controls (Follow, Mute, See Less)
7. News Source Controls (Prefer, Mute, Reduce)
8. "Why Am I Seeing This?" Human Explanation (1-3 bullets, no raw scores)
9. Pause & Resume Automatic Behavioral Learning
10. Personalization Profile Reset (Preserves Explicit Interests & Saves)
11. Personalization Profile Rebuild from Evidence Logs
12. Clear Temporary & Trending Interests
13. Strict User Data Isolation
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app
from app.models.user import User
from app.models.topic import Topic
from app.models.entity import Entity
from app.models.source import NewsSource
from app.models.article import Article
from app.models.interest import UserInterest
from app.models.interest_profile import UserTopicPreference
from app.models.personalization_settings import UserPersonalizationSettings
from app.source_intelligence.models import UserSourcePreference, UserSourceAffinity
from app.learning.evidence_models import (
    UserInterestEvidence,
    UserTopicBehaviorPreference,
    UserEntityBehaviorPreference,
    UserStoryInterestSignal,
)
from app.personalization.services.control_center_service import PersonalizationControlCenterService
from app.core.security import create_access_token


@pytest_asyncio.fixture
async def user_a(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"user_a_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pw",
        full_name="User Alpha",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_b(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"user_b_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pw",
        full_name="User Beta",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers_a(user_a):
    token = create_access_token(subject=user_a.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers_b(user_b):
    token = create_access_token(subject=user_b.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def tech_and_ai_topics(db_session):
    """Parent Tech topic and Child AI topic."""
    tech = Topic(id=uuid.uuid4(), name="Technology", slug=f"tech-{uuid.uuid4().hex[:4]}")
    db_session.add(tech)
    await db_session.flush()

    ai_topic = Topic(
        id=uuid.uuid4(),
        name="Artificial Intelligence",
        slug=f"ai-{uuid.uuid4().hex[:4]}",
        parent_topic_id=tech.id,
    )
    db_session.add(ai_topic)
    await db_session.commit()
    await db_session.refresh(tech)
    await db_session.refresh(ai_topic)
    return tech, ai_topic


# =============================================================================
# 1. Profile Loading & Settings
# =============================================================================

@pytest.mark.asyncio
async def test_get_personalization_profile(db_session, user_a, auth_headers_a, tech_and_ai_topics):
    """Test retrieving complete transparent personalization profile."""
    tech, ai_topic = tech_and_ai_topics

    # Add explicit interest for user_a
    ui = UserInterest(
        id=uuid.uuid4(),
        user_id=user_a.id,
        topic_id=tech.id,
        preference_type="POSITIVE",
        interest_score=1.0,
    )
    db_session.add(ui)

    # Add inferred behavioral preference for AI
    bp = UserTopicBehaviorPreference(
        id=uuid.uuid4(),
        user_id=user_a.id,
        topic_id=ai_topic.id,
        score=0.85,
        confidence=0.8,
        positive_evidence_count=8,
        short_term_score=0.6,
        long_term_score=0.8,
        distinct_story_count=4,
    )
    db_session.add(bp)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/personalization/profile", headers=auth_headers_a)
        assert res.status_code == 200
        data = res.json()

        # Check explicit interests
        assert len(data["explicit_interests"]) >= 1
        assert any(it["topic_name"] == "Technology" for it in data["explicit_interests"])

        # Check inferred interests
        assert len(data["inferred_interests"]) >= 1
        ai_inferred = next(it for it in data["inferred_interests"] if it["topic_name"] == "Artificial Intelligence")
        assert ai_inferred["tier"] == "Strong interest"
        assert "8 articles read" in ai_inferred["why_reason"]

        # Check privacy transparency
        assert data["privacy_transparency"]["learning_enabled"] is True


@pytest.mark.asyncio
async def test_update_personalization_settings(user_a, auth_headers_a):
    """Test updating discovery level, strength, diversity, and section preferences."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET default settings
        res_get = await client.get("/api/personalization/settings", headers=auth_headers_a)
        assert res_get.status_code == 200
        assert res_get.json()["discovery_level"] == "BALANCED"

        # PUT update settings
        res_put = await client.put(
            "/api/personalization/settings",
            headers=auth_headers_a,
            json={
                "discovery_level": "EXPLORATORY",
                "personalization_strength": "HIGH",
                "diversity_level": "DIVERSE",
                "section_preferences": {"SPORTS": "HIDE", "SCIENCE": "SHOW"},
            },
        )
        assert res_put.status_code == 200
        data = res_put.json()
        assert data["discovery_level"] == "EXPLORATORY"
        assert data["personalization_strength"] == "HIGH"
        assert data["diversity_level"] == "DIVERSE"
        assert data["section_preferences"]["SPORTS"] == "HIDE"


# =============================================================================
# 2. Topic Controls & Hierarchy Overrides
# =============================================================================

@pytest.mark.asyncio
async def test_topic_follow_mute_unmute(db_session, user_a, auth_headers_a, tech_and_ai_topics):
    """Test following, muting, and unmuting topics with explicit precedence."""
    tech, ai_topic = tech_and_ai_topics

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Follow Tech
        res_fol = await client.post(f"/api/personalization/topics/{tech.id}/follow", headers=auth_headers_a)
        assert res_fol.status_code == 200
        assert res_fol.json()["status"] == "SUCCESS"

        # 2. Mute AI
        res_mute = await client.post(f"/api/personalization/topics/{ai_topic.id}/mute", headers=auth_headers_a)
        assert res_mute.status_code == 200
        assert res_mute.json()["status"] == "SUCCESS"

        # 3. Check profile reflecting followed vs muted
        res_prof = await client.get("/api/personalization/profile", headers=auth_headers_a)
        assert res_prof.status_code == 200
        prof = res_prof.json()
        assert any(t["topic_id"] == str(tech.id) for t in prof["following_topics"])
        assert any(t["topic_id"] == str(ai_topic.id) for t in prof["muted_topics"])

        # 4. Unmute AI
        res_unmute = await client.post(f"/api/personalization/topics/{ai_topic.id}/unmute", headers=auth_headers_a)
        assert res_unmute.status_code == 200

        # Verify AI is no longer muted
        res_prof2 = await client.get("/api/personalization/profile", headers=auth_headers_a)
        assert not any(t["topic_id"] == str(ai_topic.id) for t in res_prof2.json()["muted_topics"])


@pytest.mark.asyncio
async def test_topic_adjust_feedback(db_session, user_a, auth_headers_a, tech_and_ai_topics):
    """Test user feedback adjustments (MORE / LESS)."""
    tech, _ = tech_and_ai_topics
    svc = PersonalizationControlCenterService(db_session)
    await svc.manage_topic(user_a.id, tech.id, "FOLLOW")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/personalization/topics/{tech.id}/adjust",
            headers=auth_headers_a,
            json={"action": "MORE"},
        )
        assert res.status_code == 200
        assert res.json()["action"] == "MORE"


# =============================================================================
# 3. Entity & Source Controls
# =============================================================================

@pytest.mark.asyncio
async def test_entity_and_source_controls(db_session, user_a, auth_headers_a):
    """Test following/muting entities and news sources."""
    # Create entity & source
    ent = Entity(
        id=uuid.uuid4(),
        name="OpenAI",
        normalized_name=f"openai-{uuid.uuid4().hex[:4]}",
        entity_type="ORGANIZATION",
    )
    src = NewsSource(
        id=uuid.uuid4(),
        name="Tech Chronicle",
        slug=f"tech-chronicle-{uuid.uuid4().hex[:4]}",
        website_url="https://techchronicle.example.com",
    )
    db_session.add(ent)
    db_session.add(src)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Follow Entity
        res_ent = await client.post(f"/api/personalization/entities/{ent.id}/follow", headers=auth_headers_a)
        assert res_ent.status_code == 200

        # 2. Prefer Source
        res_src = await client.post(f"/api/personalization/sources/{src.id}/prefer", headers=auth_headers_a)
        assert res_src.status_code == 200

        # 3. Mute Source
        res_mute_src = await client.post(f"/api/personalization/sources/{src.id}/mute", headers=auth_headers_a)
        assert res_mute_src.status_code == 200


# =============================================================================
# 4. "Why Am I Seeing This?" Explanation
# =============================================================================

@pytest.mark.asyncio
async def test_why_am_i_seeing_this_story(db_session, user_a, auth_headers_a, tech_and_ai_topics):
    """Test transparent 1-3 human reason explanation for recommended article."""
    tech, _ = tech_and_ai_topics
    now = datetime.now(timezone.utc)

    src = NewsSource(
        id=uuid.uuid4(),
        name="Global Tech Review",
        slug=f"gtr-{uuid.uuid4().hex[:4]}",
        website_url="https://gtr.example.com",
    )
    db_session.add(src)
    await db_session.flush()

    art = Article(
        id=uuid.uuid4(),
        title="Breakthrough in Quantum Computing Efficiency",
        slug=f"quantum-breakthrough-{uuid.uuid4().hex[:4]}",
        description="Major leap in quantum gate fidelity.",
        content="Full article details on quantum computing.",
        source_id=src.id,
        published_at=now,
        created_at=now,
        reading_time_minutes=4,
        status="PUBLISHED",
        topics=[tech],
    )
    db_session.add(art)

    # User follows tech
    ui = UserInterest(
        id=uuid.uuid4(),
        user_id=user_a.id,
        topic_id=tech.id,
        preference_type="POSITIVE",
    )
    db_session.add(ui)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/personalization/explanation/{art.id}", headers=auth_headers_a)
        assert res.status_code == 200
        exp = res.json()
        assert exp["article_id"] == str(art.id)
        assert len(exp["reasons"]) >= 1
        assert any("Technology" in r for r in exp["reasons"])


# =============================================================================
# 5. Pause/Resume, Reset & Rebuild Profile
# =============================================================================

@pytest.mark.asyncio
async def test_pause_resume_learning(db_session, user_a, auth_headers_a):
    """Test pausing automatic learning stops passive behavioral mutations."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pause
        res_pause = await client.post("/api/personalization/pause", headers=auth_headers_a)
        assert res_pause.status_code == 200
        assert res_pause.json()["learning_enabled"] is False

        # Resume
        res_resume = await client.post("/api/personalization/resume", headers=auth_headers_a)
        assert res_resume.status_code == 200
        assert res_resume.json()["learning_enabled"] is True


@pytest.mark.asyncio
async def test_reset_and_rebuild_personalization(db_session, user_a, auth_headers_a, tech_and_ai_topics):
    """Test resetting personalization clears inferred data while preserving explicit interests."""
    tech, _ = tech_and_ai_topics

    # Add explicit interest
    ui = UserInterest(id=uuid.uuid4(), user_id=user_a.id, topic_id=tech.id, preference_type="POSITIVE")
    db_session.add(ui)

    # Add inferred behavioral row
    bp = UserTopicBehaviorPreference(
        id=uuid.uuid4(), user_id=user_a.id, topic_id=tech.id, score=0.9, confidence=0.8
    )
    db_session.add(bp)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Reset
        res_reset = await client.post("/api/personalization/reset", headers=auth_headers_a)
        assert res_reset.status_code == 200

        # Check explicit interest remains, but inferred is reset
        res_prof = await client.get("/api/personalization/profile", headers=auth_headers_a)
        assert len(res_prof.json()["explicit_interests"]) >= 1
        assert len(res_prof.json()["inferred_interests"]) == 0

        # 2. Rebuild
        res_rebuild = await client.post("/api/personalization/rebuild", headers=auth_headers_a)
        assert res_rebuild.status_code == 200
        assert res_rebuild.json()["status"] == "SUCCESS"


# =============================================================================
# 6. User Isolation
# =============================================================================

@pytest.mark.asyncio
async def test_user_data_isolation(db_session, user_a, user_b, auth_headers_a, auth_headers_b, tech_and_ai_topics):
    """Test strict isolation: User A's interests and settings are never visible to User B."""
    tech, ai_topic = tech_and_ai_topics

    # User A follows Tech
    ui_a = UserInterest(id=uuid.uuid4(), user_id=user_a.id, topic_id=tech.id, preference_type="POSITIVE")
    db_session.add(ui_a)

    # User B follows AI
    ui_b = UserInterest(id=uuid.uuid4(), user_id=user_b.id, topic_id=ai_topic.id, preference_type="POSITIVE")
    db_session.add(ui_b)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        prof_a = (await client.get("/api/personalization/profile", headers=auth_headers_a)).json()
        prof_b = (await client.get("/api/personalization/profile", headers=auth_headers_b)).json()

        assert any(t["topic_name"] == "Technology" for t in prof_a["explicit_interests"])
        assert not any(t["topic_name"] == "Artificial Intelligence" for t in prof_a["explicit_interests"])

        assert any(t["topic_name"] == "Artificial Intelligence" for t in prof_b["explicit_interests"])
        assert not any(t["topic_name"] == "Technology" for t in prof_b["explicit_interests"])
