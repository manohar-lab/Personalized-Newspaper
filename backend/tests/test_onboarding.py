import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_onboarding_flow():
    email = f"onboard_{uuid.uuid4().hex[:8]}@example.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register user
        reg_resp = await client.post("/api/auth/register", json={
            "email": email,
            "password": "SecurePassword123!",
            "full_name": "Onboarding User"
        })
        token = reg_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Submit Onboarding Interests
        onboard_resp = await client.post(
            "/api/onboarding/interests",
            headers=headers,
            json={
                "positive_topics": [
                    "artificial-intelligence",
                    "machine-learning",
                    "programming",
                    "startups"
                ],
                "negative_topics": [
                    "sports",
                    "entertainment"
                ]
            }
        )
        assert onboard_resp.status_code == 201
        interests = onboard_resp.json()
        assert len(interests) == 6

        pos_interests = [i for i in interests if i["preference_type"] == "POSITIVE"]
        neg_interests = [i for i in interests if i["preference_type"] == "NEGATIVE"]

        assert len(pos_interests) == 4
        assert len(neg_interests) == 2

        for item in interests:
            assert item["interest_score"] == 0.80
            assert item["source"] == "ONBOARDING"

        # Check retrieval via /me/interests
        get_resp = await client.get("/api/users/me/interests", headers=headers)
        assert get_resp.status_code == 200
        assert len(get_resp.json()) == 6

        # Test Invalid Topic Slug in Onboarding
        invalid_resp = await client.post(
            "/api/onboarding/interests",
            headers=headers,
            json={
                "positive_topics": ["fake-nonexistent-topic"],
                "negative_topics": []
            }
        )
        assert invalid_resp.status_code == 400
        assert "Invalid topic slugs" in invalid_resp.json()["detail"]
