"""
Live Authentication Verification Script for QueueLess.
Tests against the live running FastAPI server on http://127.0.0.1:8000.
Never prints passwords, secrets, or full access tokens.
"""

import sys
import httpx
from app.config import settings

BASE_URL = "http://127.0.0.1:8000"


def run_live_verification():
    print("=" * 65)
    print("QueueLess: Live Authentication Verification Against MySQL")
    print("=" * 65)

    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 1. Health check verification
    print("\n[STEP 1] Testing GET /api/health...")
    health_resp = client.get("/api/health")
    print(f"  • HTTP Status: {health_resp.status_code}")
    print(f"  • Response:    {health_resp.json()}")
    assert health_resp.status_code == 200, "Health check failed"
    assert health_resp.json().get("database_connected") is True, "Database not connected"

    # 2. Test login with configured admin credentials
    print("\n[STEP 2] Testing POST /api/auth/login with seeded account...")
    admin_email = settings.ADMIN_EMAIL
    admin_password = settings.ADMIN_INITIAL_PASSWORD

    if not admin_password:
        print("[ERROR] ADMIN_INITIAL_PASSWORD is not set in backend/.env.")
        sys.exit(1)

    login_resp = client.post(
        "/api/auth/login",
        json={"email": admin_email, "password": admin_password},
    )
    print(f"  • Target Account: {admin_email}")
    print(f"  • HTTP Status:    {login_resp.status_code}")

    if login_resp.status_code != 200:
        print(f"  • Login failed with status {login_resp.status_code}: {login_resp.text}")
        sys.exit(1)

    login_data = login_resp.json()
    token = login_data.get("access_token")
    token_type = login_data.get("token_type")
    user_info = login_data.get("user", {})

    print(f"  • Token Received: True (Type: {token_type}, Redacted: {token[:12]}...[REDACTED])")
    print(f"  • Authenticated User: {user_info.get('email')} (Role: {user_info.get('role')})")
    print(f"  • 'password_hash' exposed in login response: {'password_hash' in user_info}")
    assert "password_hash" not in user_info, "Security violation: password_hash was exposed in login response!"

    # 3. Test GET /api/auth/me with access token
    print("\n[STEP 3] Testing GET /api/auth/me with Bearer token...")
    me_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    print(f"  • HTTP Status: {me_resp.status_code}")
    me_data = me_resp.json()
    print(f"  • User ID:     {me_data.get('id')}")
    print(f"  • Email:       {me_data.get('email')}")
    print(f"  • Full Name:   {me_data.get('full_name')}")
    print(f"  • Role:        {me_data.get('role')}")
    print(f"  • 'password_hash' exposed in /me response: {'password_hash' in me_data}")
    assert "password_hash" not in me_data, "Security violation: password_hash was exposed in /me response!"

    # 4. Test invalid password rejection
    print("\n[STEP 4] Testing POST /api/auth/login with incorrect password...")
    bad_pw_resp = client.post(
        "/api/auth/login",
        json={"email": admin_email, "password": "DefinitelyIncorrectPassword999!"},
    )
    print(f"  • HTTP Status: {bad_pw_resp.status_code}")
    print(f"  • Response:    {bad_pw_resp.json()}")
    assert bad_pw_resp.status_code == 401, "Expected 401 for bad password"

    # 5. Test unknown account rejection (anti-enumeration check)
    print("\n[STEP 5] Testing POST /api/auth/login with unknown email...")
    unknown_resp = client.post(
        "/api/auth/login",
        json={"email": "nonexistent_account@example.local", "password": "RandomPassword123!"},
    )
    print(f"  • HTTP Status: {unknown_resp.status_code}")
    print(f"  • Response:    {unknown_resp.json()}")
    assert unknown_resp.status_code == 401, "Expected 401 for unknown user"
    assert unknown_resp.json() == bad_pw_resp.json(), "Enumeration leak: error message differs between bad password and unknown user!"

    # 6. Test unauthenticated request rejection
    print("\n[STEP 6] Testing GET /api/auth/me without token...")
    no_auth_resp = client.get("/api/auth/me")
    print(f"  • HTTP Status: {no_auth_resp.status_code}")
    assert no_auth_resp.status_code in (401, 403), "Expected 401/403 for missing token"

    print("\n" + "=" * 65)
    print("[SUCCESS] All 6 live authentication checks verified successfully against MySQL!")
    print("=" * 65)


if __name__ == "__main__":
    run_live_verification()
