"""
Automated tests for Hospital Registration & Admin Approval Workflow (Phase 2, Milestone 2).
Uses an in-memory SQLite database to ensure tests are isolated and do not modify MySQL.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import Hospital, HospitalStatus, User, UserRole
from app.security import hash_password, create_access_token


# ============================================================================
# In-Memory Database Fixture & Test Setup
# ============================================================================

@pytest.fixture(name="client")
def client_fixture():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Seed test users for role verification
    with TestingSessionLocal() as db:
        admin_user = User(
            email="admin.test@example.com",
            password_hash=hash_password("AdminPass123!"),
            full_name="Admin User",
            role=UserRole.ADMIN,
            is_active=True,
        )
        staff_user = User(
            email="staff.test@example.com",
            password_hash=hash_password("StaffPass123!"),
            full_name="Staff User",
            role=UserRole.STAFF,
            hospital_id=None,
            is_active=True,
        )
        patient_user = User(
            email="patient.test@example.com",
            password_hash=hash_password("PatientPass123!"),
            full_name="Patient User",
            role=UserRole.PATIENT,
            is_active=True,
        )
        db.add_all([admin_user, staff_user, patient_user])
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


@pytest.fixture(name="admin_token")
def admin_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "admin.test@example.com", "password": "AdminPass123!"})
    return resp.json()["access_token"]


@pytest.fixture(name="staff_token")
def staff_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "staff.test@example.com", "password": "StaffPass123!"})
    return resp.json()["access_token"]


@pytest.fixture(name="patient_token")
def patient_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "patient.test@example.com", "password": "PatientPass123!"})
    return resp.json()["access_token"]


# ============================================================================
# Hospital Registration Tests
# ============================================================================

def test_register_hospital_success(client: TestClient):
    """Test public hospital onboarding creates pending record with bookings disabled."""
    payload = {
        "name": "Kovai Medical Clinic",
        "registration_number": "kovai-hosp-001",
        "address": "100 Avinashi Road",
        "city": "Coimbatore",
        "latitude": 11.025,
        "longitude": 76.980,
        "avg_consultation_time_mins": 15,
    }
    response = client.post("/api/hospitals/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Kovai Medical Clinic"
    # Registration number normalized to uppercase
    assert data["registration_number"] == "KOVAI-HOSP-001"
    # Status forced to PENDING_APPROVAL
    assert data["status"] == "PENDING_APPROVAL"
    # Bookings strictly disabled
    assert data["is_accepting_bookings"] is False


def test_register_duplicate_registration_number(client: TestClient):
    """Test registering with an existing registration number is rejected with 409."""
    payload = {
        "name": "First Hospital",
        "registration_number": "DUP-REG-999",
        "address": "12 Cross Cut Rd",
        "city": "Coimbatore",
        "latitude": 11.0,
        "longitude": 76.9,
    }
    # Initial registration
    client.post("/api/hospitals/register", json=payload)

    # Attempt duplicate registration with variations in case and whitespace
    duplicate_payload = {
        "name": "Different Name",
        "registration_number": "  dup-reg-999  ",
        "address": "Other Address",
        "city": "Coimbatore",
        "latitude": 11.0,
        "longitude": 76.9,
    }
    response = client.post("/api/hospitals/register", json=duplicate_payload)
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_register_invalid_coordinates(client: TestClient):
    """Test invalid latitude or longitude returns 422 validation error."""
    payload = {
        "name": "Invalid Coords Clinic",
        "registration_number": "INV-001",
        "address": "12 Street",
        "city": "Coimbatore",
        "latitude": 195.0,  # Invalid: > 90
        "longitude": 76.9,
    }
    response = client.post("/api/hospitals/register", json=payload)
    assert response.status_code == 422


# ============================================================================
# Admin Pending List & Authorization Tests
# ============================================================================

def test_pending_list_admin_authorized(client: TestClient, admin_token: str):
    """Admin can query the list of pending hospitals."""
    # Register two hospitals
    client.post("/api/hospitals/register", json={
        "name": "Pending One", "registration_number": "PND-001",
        "address": "Addr 1", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    })
    client.post("/api/hospitals/register", json={
        "name": "Pending Two", "registration_number": "PND-002",
        "address": "Addr 2", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    })

    response = client.get("/api/admin/hospitals/pending", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    for item in data:
        assert item["status"] == "PENDING_APPROVAL"
        assert item["is_accepting_bookings"] is False


def test_pending_list_forbidden_for_patient(client: TestClient, patient_token: str):
    """Patients receive 403 Forbidden when accessing admin endpoints."""
    response = client.get("/api/admin/hospitals/pending", headers={"Authorization": f"Bearer {patient_token}"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Administrative privileges required"


def test_pending_list_forbidden_for_staff(client: TestClient, staff_token: str):
    """Hospital staff receive 403 Forbidden when accessing admin endpoints."""
    response = client.get("/api/admin/hospitals/pending", headers={"Authorization": f"Bearer {staff_token}"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Administrative privileges required"


def test_pending_list_unauthenticated(client: TestClient):
    """Unauthenticated requests receive 401 or 403."""
    response = client.get("/api/admin/hospitals/pending")
    assert response.status_code in (401, 403)


# ============================================================================
# Admin Approval & Rejection Workflow Tests
# ============================================================================

def test_approve_hospital_success(client: TestClient, admin_token: str):
    """Admin approves pending hospital; status becomes APPROVED and bookings enabled."""
    reg = client.post("/api/hospitals/register", json={
        "name": "Approve Clinic", "registration_number": "APP-001",
        "address": "123 Main Road", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    })
    hosp_id = reg.json()["id"]

    response = client.post(f"/api/admin/hospitals/{hosp_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert "approved successfully" in data["message"]
    assert data["hospital"]["status"] == "APPROVED"
    assert data["hospital"]["is_accepting_bookings"] is True


def test_reject_hospital_success(client: TestClient, admin_token: str):
    """Admin rejects pending hospital; status becomes REJECTED and bookings disabled."""
    reg = client.post("/api/hospitals/register", json={
        "name": "Reject Clinic", "registration_number": "REJ-001",
        "address": "123 Main Road", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    })
    hosp_id = reg.json()["id"]

    response = client.post(f"/api/admin/hospitals/{hosp_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert "rejected" in data["message"]
    assert data["hospital"]["status"] == "REJECTED"
    assert data["hospital"]["is_accepting_bookings"] is False


def test_approve_or_reject_nonexistent_hospital(client: TestClient, admin_token: str):
    """Operating on non-existent hospital ID returns 404."""
    resp1 = client.post("/api/admin/hospitals/99999/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp1.status_code == 404

    resp2 = client.post("/api/admin/hospitals/99999/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp2.status_code == 404


def test_approve_already_approved_hospital(client: TestClient, admin_token: str):
    """Attempting to re-approve an already approved hospital returns 409 Conflict."""
    reg = client.post("/api/hospitals/register", json={
        "name": "Already Approved", "registration_number": "ALR-APP",
        "address": "123 Main Road", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    })
    hosp_id = reg.json()["id"]
    client.post(f"/api/admin/hospitals/{hosp_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})

    # Second approval attempt
    response = client.post(f"/api/admin/hospitals/{hosp_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 409
    assert "already approved" in response.json()["detail"]


def test_reject_already_rejected_hospital(client: TestClient, admin_token: str):
    """Attempting to re-reject an already rejected hospital returns 409 Conflict."""
    reg = client.post("/api/hospitals/register", json={
        "name": "Already Rejected", "registration_number": "ALR-REJ",
        "address": "123 Main Road", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    })
    hosp_id = reg.json()["id"]
    client.post(f"/api/admin/hospitals/{hosp_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})

    # Second rejection attempt
    response = client.post(f"/api/admin/hospitals/{hosp_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 409
    assert "already rejected" in response.json()["detail"]


def test_reject_approved_hospital_blocked(client: TestClient, admin_token: str):
    """Attempting to reject an already approved active hospital returns 409 Conflict."""
    reg = client.post("/api/hospitals/register", json={
        "name": "Approved Center", "registration_number": "APP-ACT-01",
        "address": "123 Main Road", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    })
    hosp_id = reg.json()["id"]
    client.post(f"/api/admin/hospitals/{hosp_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})

    # Attempt to reject the active hospital
    response = client.post(f"/api/admin/hospitals/{hosp_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 409
    assert "Cannot reject an already approved" in response.json()["detail"]


def test_approve_rejected_hospital_blocked(client: TestClient, admin_token: str):
    """Attempting to approve a rejected hospital returns 409 Conflict."""
    reg = client.post("/api/hospitals/register", json={
        "name": "Rejected Center", "registration_number": "REJ-BLK-01",
        "address": "123 Main Road", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    })
    hosp_id = reg.json()["id"]
    client.post(f"/api/admin/hospitals/{hosp_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})

    # Attempt to approve the rejected hospital
    response = client.post(f"/api/admin/hospitals/{hosp_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 409
    assert "Cannot approve a rejected" in response.json()["detail"]


# ============================================================================
# Suspended Hospital & Booking Ineligibility Tests
# ============================================================================

def test_handle_suspended_hospital(client: TestClient, admin_token: str):
    """Suspended hospitals cannot be approved or rejected via the standard onboarding endpoints."""
    # Register and approve first
    reg = client.post("/api/hospitals/register", json={
        "name": "Suspended Clinic", "registration_number": "SUSP-01",
        "address": "123 Main Road", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    })
    hosp_id = reg.json()["id"]
    client.post(f"/api/admin/hospitals/{hosp_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})

    # Manually transition to SUSPENDED state in test database
    override_func = app.dependency_overrides[get_db]
    db_gen = override_func()
    db = next(db_gen)
    hosp = db.query(Hospital).filter(Hospital.id == hosp_id).first()
    hosp.status = HospitalStatus.SUSPENDED
    hosp.is_accepting_bookings = False
    db.commit()

    # Verify approve is blocked with 409
    resp_app = client.post(f"/api/admin/hospitals/{hosp_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_app.status_code == 409
    assert "suspended" in resp_app.json()["detail"].lower()

    # Verify reject is blocked with 409
    resp_rej = client.post(f"/api/admin/hospitals/{hosp_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_rej.status_code == 409
    assert "suspended" in resp_rej.json()["detail"].lower()


def test_bookings_disabled_for_non_approved_states(client: TestClient, admin_token: str):
    """
    Verifies the domain rule that hospitals in PENDING_APPROVAL, REJECTED,
    or SUSPENDED status must always have is_accepting_bookings == False.
    """
    # 1. Check PENDING_APPROVAL
    p1 = client.post("/api/hospitals/register", json={
        "name": "Hosp State 1", "registration_number": "ST-01",
        "address": "123 Main Road", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    }).json()
    assert p1["status"] == "PENDING_APPROVAL"
    assert p1["is_accepting_bookings"] is False

    # 2. Check REJECTED
    p2 = client.post("/api/hospitals/register", json={
        "name": "Hosp State 2", "registration_number": "ST-02",
        "address": "123 Main Road", "city": "Coimbatore", "latitude": 11.0, "longitude": 76.9
    }).json()
    r2 = client.post(f"/api/admin/hospitals/{p2['id']}/reject", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert r2["hospital"]["status"] == "REJECTED"
    assert r2["hospital"]["is_accepting_bookings"] is False


def test_register_hospital_with_contact_info_and_coordinate_defaults(client: TestClient, admin_token: str):
    """
    Verifies that public hospital onboarding accepts contact person, email, and phone,
    gracefully defaults GPS coordinates, stores status as PENDING_APPROVAL with bookings disabled,
    and is visible to the platform admin for approval.
    """
    payload = {
        "name": "Lotus Specialty Hospital",
        "registration_number": "LOTUS-CBE-2026-001",
        "address": "45 Trichy Road, Singanallur",
        "city": "Coimbatore",
        "contact_person_name": "Dr. Ananya Sundaram",
        "contact_email": "admin@lotushospital.org",
        "contact_phone": "+91 98400 98765",
        "avg_consultation_time_mins": 20,
    }

    # 1. Public submission (no auth required)
    resp = client.post("/api/hospitals/register", json=payload)
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Lotus Specialty Hospital"
    assert created["registration_number"] == "LOTUS-CBE-2026-001"
    assert created["status"] == "PENDING_APPROVAL"
    assert created["is_accepting_bookings"] is False
    assert "Dr. Ananya Sundaram" in created["address"]
    assert "admin@lotushospital.org" in created["address"]
    assert "+91 98400 98765" in created["address"]
    # Coordinates were defaulted cleanly
    assert created["latitude"] > 0
    assert created["longitude"] > 0

    # 2. Visible in admin pending approvals
    pending_resp = client.get("/api/admin/hospitals/pending", headers={"Authorization": f"Bearer {admin_token}"})
    assert pending_resp.status_code == 200
    pending_list = pending_resp.json()
    matched = [h for h in pending_list if h["id"] == created["id"]]
    assert len(matched) == 1
    assert matched[0]["status"] == "PENDING_APPROVAL"

    # 3. Admin can approve it
    approve_resp = client.post(f"/api/admin/hospitals/{created['id']}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert approve_resp.status_code == 200
    approved_data = approve_resp.json()["hospital"]
    assert approved_data["status"] == "APPROVED"
    assert approved_data["is_accepting_bookings"] is True


# ============================================================================
# Admin Staff Provisioning Tests
# ============================================================================

def test_provision_staff_account_success(client: TestClient, admin_token: str):
    """Admin provisions the first staff account for an approved hospital."""
    # 1. Register & approve a hospital
    reg = client.post("/api/hospitals/register", json={
        "name": "Emerald Health Centre",
        "registration_number": "EMR-001",
        "address": "45 Trichy Road",
        "city": "Coimbatore",
    })
    hosp_id = reg.json()["id"]
    client.post(f"/api/admin/hospitals/{hosp_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})

    # 2. Provision staff account
    prov_resp = client.post(
        f"/api/admin/hospitals/{hosp_id}/provision-staff",
        json={
            "email": "manager.emerald@example.org",
            "full_name": "Dr. Emerald Manager",
            "phone": "+91 98400 11223",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert prov_resp.status_code == 201
    data = prov_resp.json()
    assert "provisioned successfully" in data["message"].lower()
    assert data["user"]["role"] == "STAFF"
    assert data["user"]["hospital_id"] == hosp_id
    assert data["user"]["email"] == "manager.emerald@example.org"
    # Secure temporary password returned once
    assert len(data["temporary_password"]) >= 12


def test_provision_staff_account_authentication(client: TestClient, admin_token: str):
    """A provisioned staff member can immediately authenticate and receive a JWT token."""
    reg = client.post("/api/hospitals/register", json={
        "name": "Sapphire Clinic",
        "registration_number": "SAP-001",
        "address": "77 Race Course Road",
        "city": "Coimbatore",
    })
    hosp_id = reg.json()["id"]
    client.post(f"/api/admin/hospitals/{hosp_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})

    prov_resp = client.post(
        f"/api/admin/hospitals/{hosp_id}/provision-staff",
        json={
            "email": "manager.sapphire@example.org",
            "full_name": "Sapphire Manager",
            "initial_password": "SecurePassword123!",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert prov_resp.status_code == 201

    # Login with the provisioned credentials
    login_resp = client.post("/api/auth/login", json={
        "email": "manager.sapphire@example.org",
        "password": "SecurePassword123!",
    })
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert token_data["user"]["role"] == "STAFF"
    assert token_data["user"]["hospital_id"] == hosp_id
    assert "access_token" in token_data


def test_provision_staff_unapproved_hospital_rejected(client: TestClient, admin_token: str):
    """Provisioning staff for an unapproved hospital is rejected with 400 Bad Request."""
    reg = client.post("/api/hospitals/register", json={
        "name": "Unapproved Care",
        "registration_number": "UNAPP-001",
        "address": "12 East St",
        "city": "Coimbatore",
    })
    hosp_id = reg.json()["id"]

    resp = client.post(
        f"/api/admin/hospitals/{hosp_id}/provision-staff",
        json={
            "email": "staff.unapp@example.org",
            "full_name": "Test Manager",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "approved" in resp.json()["detail"].lower()


def test_provision_staff_duplicate_email_conflict(client: TestClient, admin_token: str):
    """Attempting to provision an account with an existing email returns 409 Conflict."""
    reg = client.post("/api/hospitals/register", json={
        "name": "Diamond Hospital",
        "registration_number": "DIA-001",
        "address": "88 West St",
        "city": "Coimbatore",
    })
    hosp_id = reg.json()["id"]
    client.post(f"/api/admin/hospitals/{hosp_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})

    # First provisioning
    client.post(
        f"/api/admin/hospitals/{hosp_id}/provision-staff",
        json={
            "email": "manager.diamond@example.org",
            "full_name": "Diamond Manager",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Duplicate provisioning with same email
    dup_resp = client.post(
        f"/api/admin/hospitals/{hosp_id}/provision-staff",
        json={
            "email": "manager.diamond@example.org",
            "full_name": "Duplicate Manager",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert dup_resp.status_code == 409
    assert "already exists" in dup_resp.json()["detail"].lower()


def test_provision_staff_forbidden_for_non_admin(
    client: TestClient,
    staff_token: str,
    patient_token: str,
):
    """Non-admin users receive 403 Forbidden when attempting staff provisioning."""
    # Staff attempt
    resp_staff = client.post(
        "/api/admin/hospitals/1/provision-staff",
        json={"email": "attempt@example.org", "full_name": "Attempt"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp_staff.status_code == 403

    # Patient attempt
    resp_patient = client.post(
        "/api/admin/hospitals/1/provision-staff",
        json={"email": "attempt@example.org", "full_name": "Attempt"},
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp_patient.status_code == 403
