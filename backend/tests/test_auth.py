import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_auth_flow():
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register User
        reg_resp = await client.post("/api/auth/register", json={
            "email": unique_email,
            "password": password,
            "full_name": "Test User"
        })
        assert reg_resp.status_code == 201, reg_resp.text
        reg_data = reg_resp.json()
        assert "access_token" in reg_data
        assert reg_data["user"]["email"] == unique_email
        assert reg_data["user"]["full_name"] == "Test User"
        token = reg_data["access_token"]

        # 2. Prevent Duplicate Email Registration
        dup_resp = await client.post("/api/auth/register", json={
            "email": unique_email,
            "password": password,
            "full_name": "Duplicate User"
        })
        assert dup_resp.status_code == 409

        # 3. Login
        login_resp = await client.post("/api/auth/login", json={
            "email": unique_email,
            "password": password
        })
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        assert "access_token" in login_data

        # 4. Invalid Login Password
        invalid_pw_resp = await client.post("/api/auth/login", json={
            "email": unique_email,
            "password": "WrongPassword!"
        })
        assert invalid_pw_resp.status_code == 401

        # 5. Invalid Login Email
        invalid_email_resp = await client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": password
        })
        assert invalid_email_resp.status_code == 401

        # 6. Authenticated /me
        me_resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["email"] == unique_email

        # 7. Unauthorized /me without token
        unauth_me = await client.get("/api/auth/me")
        assert unauth_me.status_code == 401
