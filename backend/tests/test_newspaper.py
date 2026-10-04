import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_newspaper_personalization_flow():
    unique_email = f"news_user_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Unauthorized check
        unauth_resp = await client.get("/api/newspaper")
        assert unauth_resp.status_code == 401

        # 2. Register new user without interests yet
        reg_resp = await client.post("/api/auth/register", json={
            "email": unique_email,
            "password": password,
            "full_name": "Newspaper Reader"
        })
        token = reg_resp.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 3. Request newspaper for user with no interests
        empty_news_resp = await client.get("/api/newspaper", headers=auth_headers)
        assert empty_news_resp.status_code == 200
        empty_news_data = empty_news_resp.json()
        assert empty_news_data["has_interests"] is False
        assert "Newspaper Reader" in empty_news_data["user"]["name"]

        # 4. Onboard user with Positive topics (Artificial Intelligence, Cybersecurity) and Negative topic (Science)
        onboard_resp = await client.post("/api/onboarding/interests", json={
            "positive_topics": ["artificial-intelligence", "cybersecurity"],
            "negative_topics": ["science"]
        }, headers=auth_headers)
        assert onboard_resp.status_code == 201

        # 5. Fetch personalized newspaper
        news_resp = await client.get("/api/newspaper", headers=auth_headers)
        assert news_resp.status_code == 200
        news_data = news_resp.json()

        assert news_data["has_interests"] is True
        assert "Artificial Intelligence" in news_data["curation_summary"]
        assert "Cybersecurity" in news_data["curation_summary"]

        # Sections must match positive interests
        section_slugs = [s["topic"]["slug"] for s in news_data["sections"]]
        assert "artificial-intelligence" in section_slugs
        assert "cybersecurity" in section_slugs
        assert "science" not in section_slugs  # Negative interest should NOT have its own positive section

        # Check featured article is present and has positive relevance
        assert news_data["featured_article"] is not None
        assert news_data["featured_article"]["relevance_score"] is not None
        assert news_data["featured_article"]["relevance_score"] > 0

        # 6. Test Not Interested removal from newspaper
        featured_id = news_data["featured_article"]["id"]
        ni_resp = await client.post(f"/api/articles/{featured_id}/not-interested", headers=auth_headers)
        assert ni_resp.status_code == 200

        # Refetch newspaper: the article marked not interested should no longer be featured or appear in sections
        refetched_news = await client.get("/api/newspaper", headers=auth_headers)
        refetched_data = refetched_news.json()
        if refetched_data["featured_article"]:
            assert refetched_data["featured_article"]["id"] != featured_id
        for sec in refetched_data["sections"]:
            for a in sec["articles"]:
                assert a["id"] != featured_id
