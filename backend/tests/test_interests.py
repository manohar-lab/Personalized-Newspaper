import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

async def create_user_and_get_token(client: AsyncClient, name: str) -> tuple[str, str]:
    email = f"{name}_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post("/api/auth/register", json={
        "email": email,
        "password": "SecurePassword123!",
        "full_name": name
    })
    token = resp.json()["access_token"]
    return email, token

@pytest.mark.asyncio
async def test_user_interests_crud_and_isolation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, token1 = await create_user_and_get_token(client, "UserOne")
        _, token2 = await create_user_and_get_token(client, "UserTwo")

        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        # 1. Add Positive Interest for User 1
        post_resp = await client.post(
            "/api/users/me/interests",
            headers=headers1,
            json={
                "topic_slug": "artificial-intelligence",
                "interest_score": 0.95,
                "preference_type": "POSITIVE"
            }
        )
        assert post_resp.status_code == 201
        item1 = post_resp.json()
        assert item1["topic_slug"] == "artificial-intelligence"
        assert item1["interest_score"] == 0.95
        assert item1["preference_type"] == "POSITIVE"

        # 2. Add Negative Interest for User 1
        neg_resp = await client.post(
            "/api/users/me/interests",
            headers=headers1,
            json={
                "topic_slug": "sports",
                "interest_score": 0.10,
                "preference_type": "NEGATIVE"
            }
        )
        assert neg_resp.status_code == 201
        item_neg = neg_resp.json()
        assert item_neg["preference_type"] == "NEGATIVE"

        # 3. Retrieve User 1 Interests
        get_resp1 = await client.get("/api/users/me/interests", headers=headers1)
        assert get_resp1.status_code == 200
        user1_interests = get_resp1.json()
        assert len(user1_interests) == 2

        # 4. User 2 should have 0 interests (User Isolation)
        get_resp2 = await client.get("/api/users/me/interests", headers=headers2)
        assert get_resp2.status_code == 200
        assert len(get_resp2.json()) == 0

        # 5. Update Interest for User 1
        update_resp = await client.post(
            "/api/users/me/interests",
            headers=headers1,
            json={
                "topic_slug": "artificial-intelligence",
                "interest_score": 0.99,
                "preference_type": "POSITIVE"
            }
        )
        assert update_resp.status_code == 201
        assert update_resp.json()["interest_score"] == 0.99

        # 6. Bulk Update Interests
        bulk_resp = await client.put(
            "/api/users/me/interests",
            headers=headers1,
            json={
                "interests": [
                    {
                        "topic_slug": "artificial-intelligence",
                        "interest_score": 0.90,
                        "preference_type": "POSITIVE"
                    },
                    {
                        "topic_slug": "machine-learning",
                        "interest_score": 0.85,
                        "preference_type": "POSITIVE"
                    }
                ]
            }
        )
        assert bulk_resp.status_code == 200
        assert len(bulk_resp.json()) == 2

        # 7. Invalid Interest Score (> 1.0)
        invalid_score_resp = await client.post(
            "/api/users/me/interests",
            headers=headers1,
            json={
                "topic_slug": "cybersecurity",
                "interest_score": 1.5,
                "preference_type": "POSITIVE"
            }
        )
        assert invalid_score_resp.status_code == 422

        # 8. Remove Interest for User 1
        del_resp = await client.delete(
            "/api/users/me/interests/sports",
            headers=headers1
        )
        assert del_resp.status_code == 200

        # Verify sports removed from User 1
        get_after_del = await client.get("/api/users/me/interests", headers=headers1)
        slugs_left = [i["topic_slug"] for i in get_after_del.json()]
        assert "sports" not in slugs_left
