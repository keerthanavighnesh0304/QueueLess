"""
Unit tests for the safe, idempotent hosted database initialization tool.
Validates:
1. Rejection of local loopback/localhost targets before any connection attempt.
2. Mandatory enforcement of the '--confirm-hosted' flag.
3. Strict validation of non-empty credentials.
4. Schema generation and entity-level idempotent seeding without record alteration.
5. Future-dated consultation session generation across today + 3 upcoming calendar days.
6. Bcrypt password hashing and secret isolation.
7. Support for discrete Render environment variables and explicit DATABASE_URL configs.
"""

from datetime import date, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    ConsultationSession,
    Department,
    Doctor,
    Hospital,
    HospitalStatus,
    SessionStatus,
    User,
    UserRole,
)
from app.security import verify_password
from init_hosted_db import (
    get_or_create_admin,
    initialize_hosted_database,
    resolve_database_config,
    seed_demo_entities,
    validate_hosted_target,
    validate_seed_credentials,
)


def test_refuses_when_missing_confirm_hosted_flag():
    """Execution must immediately fail if --confirm-hosted is not passed."""
    with pytest.raises(ValueError, match="Missing required confirmation flag '--confirm-hosted'"):
        initialize_hosted_database(
            database_url="mysql+pymysql://avnadmin:pass@aivencloud.com:12345/defaultdb",
            confirm_hosted=False,
        )


def test_refuses_localhost_and_loopback_targets():
    """Safety check must reject any localhost, loopback, or local addresses."""
    loopback_examples = [
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "",
        "None",
        "my-laptop.local",
    ]

    for host in loopback_examples:
        with pytest.raises(ValueError, match="localhost/loopback address"):
            validate_hosted_target(host)


def test_refuses_when_credentials_missing(monkeypatch):
    """Missing or empty credential environment variables must stop execution before DB access."""
    monkeypatch.delenv("ADMIN_INITIAL_PASSWORD", raising=False)
    monkeypatch.delenv("DEMO_ACCOUNTS_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="Required credential environment variable"):
        validate_seed_credentials()

    monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", "   ")
    monkeypatch.setenv("DEMO_ACCOUNTS_PASSWORD", "valid_demo_pass")
    with pytest.raises(ValueError, match="ADMIN_INITIAL_PASSWORD"):
        validate_seed_credentials()


def test_idempotent_initialization_on_sqlite():
    """
    Simulates schema creation and seeding against an isolated database.
    Verifies that running twice causes zero errors, zero duplicates, and preserves counts.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    base_test_date = date(2026, 10, 13)

    # --- Run 1: Initial seed ---
    with TestingSession() as db:
        admin, created = get_or_create_admin(db, "AdminSecret123!", "admin@queueless.local")
        assert created is True
        assert admin.role == UserRole.ADMIN
        admin_id = admin.id

        stats1 = seed_demo_entities(db, "DemoSecret123!", base_date=base_test_date)
        assert stats1["hospitals_created"] == 3
        assert stats1["departments_created"] == 3
        assert stats1["doctors_created"] == 3
        assert stats1["users_created"] == 3
        # 3 doctors * 4 days = 12 consultation sessions
        assert stats1["sessions_created"] == 12

    # --- Run 2: Idempotent re-run on existing database ---
    with TestingSession() as db:
        admin2, created2 = get_or_create_admin(db, "DifferentPass!", "admin@queueless.local")
        assert created2 is False
        assert admin2.id == admin_id

        stats2 = seed_demo_entities(db, "DifferentPass!", base_date=base_test_date)
        assert stats2["hospitals_created"] == 0
        assert stats2["departments_created"] == 0
        assert stats2["doctors_created"] == 0
        assert stats2["users_created"] == 0
        assert stats2["sessions_created"] == 0

        # Verify aggregate counts remain unchanged
        assert db.query(Hospital).count() == 3
        assert db.query(Department).count() == 3
        assert db.query(Doctor).count() == 3
        assert db.query(User).count() == 4  # 1 admin + 2 staff + 1 patient
        assert db.query(ConsultationSession).count() == 12


def test_preserves_existing_user_password():
    """Re-running seed must never overwrite an existing user's password."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    with TestingSession() as db:
        admin1, _ = get_or_create_admin(db, "InitialStrongPassword123!", "admin@queueless.local")
        original_hash = admin1.password_hash

    with TestingSession() as db:
        admin2, created = get_or_create_admin(db, "AttemptedOverwritePassword999!", "admin@queueless.local")
        assert created is False
        assert admin2.password_hash == original_hash
        assert verify_password("InitialStrongPassword123!", admin2.password_hash) is True
        assert verify_password("AttemptedOverwritePassword999!", admin2.password_hash) is False


def test_future_consultation_sessions_dated_properly():
    """Consultation sessions must cover today and the next three calendar days."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    base_test_date = date(2026, 10, 13)
    expected_dates = {base_test_date + timedelta(days=i) for i in range(4)}

    with TestingSession() as db:
        seed_demo_entities(db, "DemoSecret123!", base_date=base_test_date)
        sessions = db.query(ConsultationSession).all()

        assert len(sessions) == 12
        actual_dates = {s.session_date for s in sessions}
        assert actual_dates == expected_dates

        # Today and tomorrow must be ACTIVE; subsequent days SCHEDULED
        active_sessions = [s for s in sessions if s.session_date in {base_test_date, base_test_date + timedelta(days=1)}]
        scheduled_sessions = [s for s in sessions if s.session_date > base_test_date + timedelta(days=1)]

        for s in active_sessions:
            assert s.status == SessionStatus.ACTIVE
        for s in scheduled_sessions:
            assert s.status == SessionStatus.SCHEDULED


def test_passwords_are_securely_hashed():
    """All seeded user passwords must be hashed using bcrypt."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)

    demo_pass = "MySecretDemoPass123!"
    with TestingSession() as db:
        get_or_create_admin(db, "AdminSecret123!", "admin@queueless.local")
        seed_demo_entities(db, demo_pass, base_date=date(2026, 10, 13))

        users = db.query(User).all()
        assert len(users) == 4

        for u in users:
            assert u.password_hash.startswith("$2b$")
            assert demo_pass not in u.password_hash
            assert "AdminSecret123!" not in u.password_hash


def test_supports_discrete_render_env_config(monkeypatch):
    """Supports discrete DB_* environment variables commonly used in Render."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("HOSTED_DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "mysql-project.aivencloud.com")
    monkeypatch.setenv("DB_PORT", "17890")
    monkeypatch.setenv("DB_USER", "avnadmin")
    monkeypatch.setenv("DB_PASSWORD", "mypassword")
    monkeypatch.setenv("DB_NAME", "defaultdb")
    monkeypatch.setenv("DB_SSL_MODE", "REQUIRED")

    url, connect_args, host = resolve_database_config()
    assert host == "mysql-project.aivencloud.com"
    assert url.startswith("mysql+pymysql://avnadmin:mypassword@mysql-project.aivencloud.com:17890/defaultdb")
    assert "ssl" in connect_args
    assert connect_args["ssl"]["check_hostname"] is True


def test_supports_explicit_database_url_render_config(monkeypatch):
    """Supports explicit DATABASE_URL string, rewriting scheme and mapping TLS parameters."""
    aiven_uri = "mysql://avnadmin:secret@mysql-service.aivencloud.com:12345/defaultdb?ssl-mode=REQUIRED&charset=utf8mb4"
    monkeypatch.setenv("DATABASE_URL", aiven_uri)

    url, connect_args, host = resolve_database_config()
    assert host == "mysql-service.aivencloud.com"
    assert url.startswith("mysql+pymysql://")
    assert "ssl-mode" not in url
    assert "ssl" in connect_args
    assert connect_args["ssl"]["check_hostname"] is True
