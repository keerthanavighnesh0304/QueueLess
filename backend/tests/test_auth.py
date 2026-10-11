"""
Automated tests for Authentication Foundation (Phase 2, Milestone 1).
Uses an in-memory SQLite database to ensure tests are isolated and do not modify MySQL.
"""

from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import User, UserRole
from app.security import hash_password, create_access_token


# ============================================================================
# In-Memory Database Fixture & Test Setup
# ============================================================================

@pytest.fixture(name="client")
def client_fixture():
    # Setup fresh in-memory database per test session using StaticPool to share connection
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Seed test users
    with TestingSessionLocal() as db:
        active_user = User(
            email="patient.test@example.com",
            password_hash=hash_password("ValidPassword123!"),
            full_name="Test Patient",
            phone="+919876543210",
            role=UserRole.PATIENT,
            hospital_id=None,
            is_active=True,
        )
        inactive_user = User(
            email="inactive.test@example.com",
            password_hash=hash_password("ValidPassword123!"),
            full_name="Inactive User",
            phone="+919876543211",
            role=UserRole.PATIENT,
            hospital_id=None,
            is_active=False,
        )
        db.add_all([active_user, inactive_user])
        db.commit()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# Test Cases
# ============================================================================

def test_login_success(client: TestClient):
    """Test successful authentication with valid credentials."""
    response = client.post(
        "/api/auth/login",
        json={"email": "patient.test@example.com", "password": "ValidPassword123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in_minutes"] > 0
    assert "user" in data
    assert data["user"]["email"] == "patient.test@example.com"
    assert data["user"]["full_name"] == "Test Patient"
    assert data["user"]["role"] == "PATIENT"
    # Verify password_hash is NEVER exposed
    assert "password_hash" not in data["user"]
    assert "password" not in data["user"]


def test_login_incorrect_password(client: TestClient):
    """Test authentication failure with incorrect password returns generic 401."""
    response = client.post(
        "/api/auth/login",
        json={"email": "patient.test@example.com", "password": "WrongPassword999!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_unknown_account(client: TestClient):
    """
    Test authentication failure with non-existent account.
    Must return identical generic error to prevent email enumeration.
    """
    response = client.post(
        "/api/auth/login",
        json={"email": "nonexistent.user@example.com", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_inactive_user(client: TestClient):
    """Test that inactive accounts are blocked from logging in."""
    response = client.post(
        "/api/auth/login",
        json={"email": "inactive.test@example.com", "password": "ValidPassword123!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_get_current_user_valid_token(client: TestClient):
    """Test protected /api/auth/me endpoint with a valid Bearer token."""
    # First log in to obtain a genuine token
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "patient.test@example.com", "password": "ValidPassword123!"},
    )
    token = login_resp.json()["access_token"]

    # Access protected route
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == "patient.test@example.com"
    assert user_data["full_name"] == "Test Patient"
    assert "password_hash" not in user_data


def test_get_current_user_invalid_token(client: TestClient):
    """Test protected endpoint rejects malformed or forged tokens."""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer forged.invalid.token.string"},
    )
    assert response.status_code == 401


def test_get_current_user_expired_token(client: TestClient):
    """Test protected endpoint rejects expired tokens."""
    # Generate token with negative expiration (expired 10 minutes ago)
    expired_token = create_access_token(
        data={"sub": "1", "email": "patient.test@example.com", "role": "PATIENT", "hospital_id": None},
        expires_delta=timedelta(minutes=-10),
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Token has expired"


def test_get_current_user_missing_token(client: TestClient):
    """Test protected endpoint rejects requests with no Authorization header."""
    response = client.get("/api/auth/me")
    assert response.status_code in (401, 403)
