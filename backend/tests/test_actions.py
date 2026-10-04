import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_user_actions_and_saved_articles():
    unique_email = f"action_user_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register user
        reg_resp = await client.post("/api/auth/register", json={
            "email": unique_email,
            "password": password,
            "full_name": "Action Tester"
        })
        assert reg_resp.status_code == 201
        token = reg_resp.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Get an article
        art_resp = await client.get("/api/articles?limit=2")
        articles = art_resp.json()["items"]
        art1_id = articles[0]["id"]
        art2_id = articles[1]["id"]

        # 1. Unauthorized action test
        unauth_save = await client.post(f"/api/articles/{art1_id}/save")
        assert unauth_save.status_code == 401

        # 2. Save Article
        save_resp = await client.post(f"/api/articles/{art1_id}/save", headers=auth_headers)
        assert save_resp.status_code == 200
        assert save_resp.json()["success"] is True
        assert save_resp.json()["action"] == "SAVE"

        # 3. Like Article
        like_resp = await client.post(f"/api/articles/{art1_id}/like", headers=auth_headers)
        assert like_resp.status_code == 200
        assert like_resp.json()["action"] == "LIKE"

        # 4. Check Article detail reflects is_saved & is_liked
        detail_resp = await client.get(f"/api/articles/{art1_id}", headers=auth_headers)
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["is_saved"] is True
        assert detail_data["is_liked"] is True

        # 5. Retrieve saved articles
        saved_resp = await client.get("/api/users/me/saved-articles", headers=auth_headers)
        assert saved_resp.status_code == 200
        saved_data = saved_resp.json()
        assert saved_data["total"] == 1
        assert saved_data["items"][0]["article"]["id"] == art1_id

        # 6. Unsave article
        unsave_resp = await client.delete(f"/api/articles/{art1_id}/save", headers=auth_headers)
        assert unsave_resp.status_code == 200
        assert unsave_resp.json()["success"] is True

        # 7. Check saved list is now empty
        saved_resp2 = await client.get("/api/users/me/saved-articles", headers=auth_headers)
        assert saved_resp2.status_code == 200
        assert saved_resp2.json()["total"] == 0

        # 8. Unlike article
        unlike_resp = await client.delete(f"/api/articles/{art1_id}/like", headers=auth_headers)
        assert unlike_resp.status_code == 200

        # 9. Mark not interested on article 2
        ni_resp = await client.post(f"/api/articles/{art2_id}/not-interested", headers=auth_headers)
        assert ni_resp.status_code == 200
        assert ni_resp.json()["action"] == "NOT_INTERESTED"

        # Check detail reflects not interested
        detail_resp2 = await client.get(f"/api/articles/{art2_id}", headers=auth_headers)
        assert detail_resp2.status_code == 200
        assert detail_resp2.json()["is_not_interested"] is True
