"""
Automated tests for Hospital, Department, Doctor, and Consultation Session APIs (Phase 2, Milestone 3).
Uses an isolated in-memory SQLite database to ensure tests run independently and never modify MySQL.
"""

from datetime import date, time, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import (
    Hospital,
    HospitalStatus,
    Department,
    Doctor,
    ConsultationSession,
    SessionStatus,
    User,
    UserRole,
)
from app.security import hash_password


# ============================================================================
# In-Memory Database Fixtures & Seeding
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

    today = date.today()
    tomorrow = today + timedelta(days=1)

    with TestingSessionLocal() as db:
        # 1. Seed Hospitals with different statuses
        h1 = Hospital(
            id=1,
            name="Coimbatore Medical Center",
            registration_number="REG-HOSP-001",
            address="100 Trichy Road",
            city="Coimbatore",
            latitude=11.0168,
            longitude=76.9558,
            status=HospitalStatus.APPROVED,
            is_accepting_bookings=True,
            avg_consultation_time_mins=15,
        )
        h2 = Hospital(
            id=2,
            name="Apex Heart Institute",
            registration_number="REG-HOSP-002",
            address="50 Anna Salai",
            city="Chennai",
            latitude=13.0827,
            longitude=80.2707,
            status=HospitalStatus.APPROVED,
            is_accepting_bookings=True,
            avg_consultation_time_mins=20,
        )
        h3 = Hospital(
            id=3,
            name="Sunrise Pending Clinic",
            registration_number="REG-HOSP-003",
            address="25 Avinashi Road",
            city="Coimbatore",
            latitude=11.0200,
            longitude=76.9600,
            status=HospitalStatus.PENDING_APPROVAL,
            is_accepting_bookings=False,
            avg_consultation_time_mins=15,
        )
        h4 = Hospital(
            id=4,
            name="Rejected Health Center",
            registration_number="REG-HOSP-004",
            address="10 Race Course",
            city="Coimbatore",
            latitude=11.0100,
            longitude=76.9500,
            status=HospitalStatus.REJECTED,
            is_accepting_bookings=False,
            avg_consultation_time_mins=15,
        )
        h5 = Hospital(
            id=5,
            name="Suspended Care Hospital",
            registration_number="REG-HOSP-005",
            address="12 Gandhipuram",
            city="Coimbatore",
            latitude=11.0250,
            longitude=76.9700,
            status=HospitalStatus.SUSPENDED,
            is_accepting_bookings=False,
            avg_consultation_time_mins=15,
        )
        db.add_all([h1, h2, h3, h4, h5])
        db.flush()

        # 2. Seed Users
        admin_user = User(
            email="admin@example.com",
            password_hash=hash_password("AdminPass123!"),
            full_name="System Admin",
            role=UserRole.ADMIN,
            is_active=True,
        )
        staff1 = User(
            email="staff1@example.com",
            password_hash=hash_password("StaffPass123!"),
            full_name="Hospital 1 Staff",
            role=UserRole.STAFF,
            hospital_id=1,
            is_active=True,
        )
        staff2 = User(
            email="staff2@example.com",
            password_hash=hash_password("StaffPass123!"),
            full_name="Hospital 2 Staff",
            role=UserRole.STAFF,
            hospital_id=2,
            is_active=True,
        )
        patient_user = User(
            email="patient@example.com",
            password_hash=hash_password("PatientPass123!"),
            full_name="Patient User",
            role=UserRole.PATIENT,
            is_active=True,
        )
        db.add_all([admin_user, staff1, staff2, patient_user])
        db.flush()

        # 3. Seed Departments
        dept_cardiology = Department(
            id=1,
            hospital_id=1,
            name="Cardiology",
            description="Heart care and diagnostics",
        )
        dept_neurology = Department(
            id=2,
            hospital_id=1,
            name="Neurology",
            description="Brain and nerve care",
        )
        dept_pediatrics = Department(
            id=3,
            hospital_id=2,
            name="Pediatrics",
            description="Child health",
        )
        db.add_all([dept_cardiology, dept_neurology, dept_pediatrics])
        db.flush()

        # 4. Seed Doctors
        doc1 = Doctor(
            id=1,
            hospital_id=1,
            department_id=1,
            full_name="Dr. S. Kulkarni",
            qualification="MBBS, MD, DM",
            specialization="Cardiology",
            ticket_prefix="CARD",
            avg_consultation_time_mins=15,
            is_active=True,
        )
        doc2 = Doctor(
            id=2,
            hospital_id=1,
            department_id=2,
            full_name="Dr. V. Menon",
            qualification="MBBS, MCh",
            specialization="Neurology",
            ticket_prefix="NEURO",
            avg_consultation_time_mins=20,
            is_active=True,
        )
        doc3_inactive = Doctor(
            id=3,
            hospital_id=1,
            department_id=1,
            full_name="Dr. R. Gupta (Inactive)",
            qualification="MBBS",
            specialization="Cardiology",
            ticket_prefix="CARD",
            avg_consultation_time_mins=15,
            is_active=False,
        )
        doc4_h2 = Doctor(
            id=4,
            hospital_id=2,
            department_id=3,
            full_name="Dr. N. Iyer",
            qualification="MBBS, MD (Pediatrics)",
            specialization="Pediatrics",
            ticket_prefix="PED",
            avg_consultation_time_mins=12,
            is_active=True,
        )
        db.add_all([doc1, doc2, doc3_inactive, doc4_h2])
        db.flush()

        # 5. Seed Consultation Sessions
        sess1 = ConsultationSession(
            id=1,
            hospital_id=1,
            doctor_id=1,
            session_name="Morning Cardiology OPD",
            session_date=tomorrow,
            start_time=time(9, 0),
            end_time=time(12, 0),
            status=SessionStatus.SCHEDULED,
            last_sequence_number=0,
            max_capacity=30,
        )
        sess2_h2 = ConsultationSession(
            id=2,
            hospital_id=2,
            doctor_id=4,
            session_name="Morning Pediatrics OPD",
            session_date=tomorrow,
            start_time=time(10, 0),
            end_time=time(13, 0),
            status=SessionStatus.ACTIVE,
            last_sequence_number=5,
            max_capacity=25,
        )
        db.add_all([sess1, sess2_h2])
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
    resp = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "AdminPass123!"})
    return resp.json()["access_token"]


@pytest.fixture(name="staff1_token")
def staff1_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "staff1@example.com", "password": "StaffPass123!"})
    return resp.json()["access_token"]


@pytest.fixture(name="staff2_token")
def staff2_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "staff2@example.com", "password": "StaffPass123!"})
    return resp.json()["access_token"]


@pytest.fixture(name="patient_token")
def patient_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "patient@example.com", "password": "PatientPass123!"})
    return resp.json()["access_token"]


# ============================================================================
# 1. Public Hospital Listing Tests
# ============================================================================

def test_list_approved_hospitals_only(client: TestClient):
    """Verifies that only approved hospitals accepting bookings appear in public listing."""
    resp = client.get("/api/hospitals")
    assert resp.status_code == 200
    data = resp.json()

    # Out of 5 hospitals, only Hospital 1 and Hospital 2 are approved & accepting bookings
    assert len(data) == 2
    names = [h["name"] for h in data]
    assert "Coimbatore Medical Center" in names
    assert "Apex Heart Institute" in names
    assert "Sunrise Pending Clinic" not in names
    assert "Rejected Health Center" not in names
    assert "Suspended Care Hospital" not in names

    for h in data:
        assert h["status"] == "APPROVED"
        assert h["is_accepting_bookings"] is True


def test_list_hospitals_city_filter(client: TestClient):
    """Verifies that filtering by city works correctly."""
    resp = client.get("/api/hospitals?city=Chennai")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Apex Heart Institute"

    resp_cbe = client.get("/api/hospitals?city=Coimbatore")
    assert resp_cbe.status_code == 200
    data_cbe = resp_cbe.json()
    assert len(data_cbe) == 1
    assert data_cbe[0]["name"] == "Coimbatore Medical Center"


def test_list_hospitals_search_filter(client: TestClient):
    """Verifies that search query matches hospital name substring."""
    resp = client.get("/api/hospitals?search=Apex")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Apex Heart Institute"


# ============================================================================
# 2. Hospital Details Tests
# ============================================================================

def test_get_hospital_details_approved(client: TestClient):
    """Verifies retrieving details of an approved hospital with its departments."""
    resp = client.get("/api/hospitals/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert data["name"] == "Coimbatore Medical Center"
    assert data["status"] == "APPROVED"
    assert "departments" in data
    assert len(data["departments"]) == 2
    dept_names = [d["name"] for d in data["departments"]]
    assert "Cardiology" in dept_names
    assert "Neurology" in dept_names


def test_get_hospital_details_pending_returns_404(client: TestClient):
    """Verifies that pending hospitals cannot be probed or viewed via public endpoint."""
    resp = client.get("/api/hospitals/3")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_get_hospital_details_rejected_returns_404(client: TestClient):
    """Verifies that rejected hospitals return 404."""
    resp = client.get("/api/hospitals/4")
    assert resp.status_code == 404


def test_get_hospital_details_nonexistent_returns_404(client: TestClient):
    """Verifies that non-existent hospital ID returns 404."""
    resp = client.get("/api/hospitals/999")
    assert resp.status_code == 404


# ============================================================================
# 3. Department Catalog Tests
# ============================================================================

def test_list_departments_success(client: TestClient):
    """Verifies listing departments belonging strictly to the requested hospital."""
    resp = client.get("/api/hospitals/1/departments")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for dept in data:
        assert dept["hospital_id"] == 1

    resp2 = client.get("/api/hospitals/2/departments")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2) == 1
    assert data2[0]["name"] == "Pediatrics"
    assert data2[0]["hospital_id"] == 2


def test_list_departments_unapproved_hospital_returns_404(client: TestClient):
    """Verifies that unapproved hospitals return 404 when querying departments."""
    resp = client.get("/api/hospitals/3/departments")
    assert resp.status_code == 404


# ============================================================================
# 4. Doctor Catalog & Relationship Validation Tests
# ============================================================================

def test_list_doctors_success(client: TestClient):
    """Verifies listing active doctors for an approved hospital."""
    resp = client.get("/api/hospitals/1/doctors")
    assert resp.status_code == 200
    data = resp.json()
    # Doctor 1 and Doctor 2 are active, Doctor 3 is inactive
    assert len(data) == 2
    doc_ids = [d["id"] for d in data]
    assert 1 in doc_ids
    assert 2 in doc_ids
    assert 3 not in doc_ids


def test_list_doctors_department_filter(client: TestClient):
    """Verifies filtering doctors by department ID."""
    resp = client.get("/api/hospitals/1/doctors?department_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["specialization"] == "Cardiology"


def test_list_doctors_mismatched_department_returns_404(client: TestClient):
    """Verifies that filtering with a department ID belonging to another hospital returns 404."""
    # Department 3 belongs to Hospital 2, queried under Hospital 1
    resp = client.get("/api/hospitals/1/doctors?department_id=3")
    assert resp.status_code == 404
    assert "department not found" in resp.json()["detail"].lower()


def test_get_doctor_details_success(client: TestClient):
    """Verifies retrieving details of an active doctor."""
    resp = client.get("/api/hospitals/1/doctors/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert data["full_name"] == "Dr. S. Kulkarni"
    assert data["hospital_id"] == 1


def test_get_doctor_wrong_hospital_returns_404(client: TestClient):
    """Verifies that accessing a doctor under the wrong hospital route returns 404."""
    # Doctor 4 belongs to Hospital 2, queried under Hospital 1
    resp = client.get("/api/hospitals/1/doctors/4")
    assert resp.status_code == 404
    assert "doctor not found" in resp.json()["detail"].lower()


def test_get_doctor_inactive_returns_404(client: TestClient):
    """Verifies that accessing an inactive doctor returns 404."""
    resp = client.get("/api/hospitals/1/doctors/3")
    assert resp.status_code == 404


# ============================================================================
# 5. Consultation Sessions Public Discovery Tests
# ============================================================================

def test_list_doctor_sessions_success(client: TestClient):
    """Verifies listing sessions for a doctor."""
    resp = client.get("/api/hospitals/1/doctors/1/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["session_name"] == "Morning Cardiology OPD"
    assert data[0]["doctor_id"] == 1
    assert data[0]["hospital_id"] == 1


def test_list_doctor_sessions_wrong_hospital_returns_404(client: TestClient):
    """Verifies that querying a doctor's sessions via another hospital returns 404."""
    # Doctor 4 belongs to Hospital 2, queried under Hospital 1
    resp = client.get("/api/hospitals/1/doctors/4/sessions")
    assert resp.status_code == 404


def test_list_hospital_sessions_success(client: TestClient):
    """Verifies listing consultation sessions for an entire hospital."""
    resp = client.get("/api/hospitals/1/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == 1


def test_get_session_details_success(client: TestClient):
    """Verifies retrieving session details by ID."""
    resp = client.get("/api/hospitals/1/sessions/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert data["session_name"] == "Morning Cardiology OPD"


def test_get_session_wrong_hospital_returns_404(client: TestClient):
    """Verifies that querying a session via the wrong hospital returns 404."""
    # Session 2 belongs to Hospital 2, queried under Hospital 1
    resp = client.get("/api/hospitals/1/sessions/2")
    assert resp.status_code == 404


# ============================================================================
# 6. Staff-Only Session Management & Hospital Isolation Tests
# ============================================================================

def test_staff_create_session_success(client: TestClient, staff1_token: str):
    """Staff of Hospital 1 can successfully schedule a session in Hospital 1."""
    tomorrow = date.today() + timedelta(days=1)
    payload = {
        "doctor_id": 2,
        "session_name": "Evening Neurology OPD",
        "session_date": str(tomorrow),
        "start_time": "16:00:00",
        "end_time": "19:00:00",
        "max_capacity": 20,
    }
    resp = client.post(
        "/api/hospitals/1/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["hospital_id"] == 1
    assert data["doctor_id"] == 2
    assert data["session_name"] == "Evening Neurology OPD"
    assert data["status"] == "SCHEDULED"


def test_staff_create_session_cross_hospital_isolation_forbidden(
    client: TestClient,
    staff1_token: str,
):
    """Staff of Hospital 1 cannot schedule sessions in Hospital 2."""
    tomorrow = date.today() + timedelta(days=1)
    payload = {
        "doctor_id": 4,
        "session_name": "Unauthorized Session",
        "session_date": str(tomorrow),
        "start_time": "14:00:00",
        "end_time": "17:00:00",
        "max_capacity": 15,
    }
    resp = client.post(
        "/api/hospitals/2/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower()


def test_admin_create_session_any_hospital(client: TestClient, admin_token: str):
    """System administrator can schedule sessions across any approved hospital."""
    tomorrow = date.today() + timedelta(days=1)
    payload = {
        "doctor_id": 4,
        "session_name": "Admin Scheduled Pediatric OPD",
        "session_date": str(tomorrow),
        "start_time": "15:00:00",
        "end_time": "18:00:00",
        "max_capacity": 25,
    }
    resp = client.post(
        "/api/hospitals/2/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["hospital_id"] == 2


def test_patient_create_session_forbidden(client: TestClient, patient_token: str):
    """Patients cannot schedule consultation sessions."""
    tomorrow = date.today() + timedelta(days=1)
    payload = {
        "doctor_id": 1,
        "session_name": "Patient Created Session",
        "session_date": str(tomorrow),
        "start_time": "14:00:00",
        "end_time": "17:00:00",
        "max_capacity": 10,
    }
    resp = client.post(
        "/api/hospitals/1/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 403


def test_unauthenticated_create_session_unauthorized(client: TestClient):
    """Unauthenticated requests cannot create sessions."""
    tomorrow = date.today() + timedelta(days=1)
    payload = {
        "doctor_id": 1,
        "session_name": "Anon Session",
        "session_date": str(tomorrow),
    }
    resp = client.post("/api/hospitals/1/sessions", json=payload)
    assert resp.status_code == 401


def test_create_session_wrong_doctor_returns_404(client: TestClient, staff1_token: str):
    """Attempting to schedule a doctor belonging to another hospital returns 404."""
    tomorrow = date.today() + timedelta(days=1)
    payload = {
        "doctor_id": 4,  # Belongs to Hospital 2
        "session_name": "Mismatched Doctor Session",
        "session_date": str(tomorrow),
        "start_time": "10:00:00",
        "end_time": "12:00:00",
    }
    resp = client.post(
        "/api/hospitals/1/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 404
    assert "doctor not found" in resp.json()["detail"].lower()


def test_create_session_inactive_doctor_returns_400(client: TestClient, staff1_token: str):
    """Attempting to schedule an inactive doctor returns 400."""
    tomorrow = date.today() + timedelta(days=1)
    payload = {
        "doctor_id": 3,  # Inactive doctor
        "session_name": "Inactive Doctor Session",
        "session_date": str(tomorrow),
        "start_time": "10:00:00",
        "end_time": "12:00:00",
    }
    resp = client.post(
        "/api/hospitals/1/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 400
    assert "inactive doctor" in resp.json()["detail"].lower()


def test_create_session_past_date_returns_400(client: TestClient, staff1_token: str):
    """Attempting to schedule a session in the past returns 400."""
    yesterday = date.today() - timedelta(days=1)
    payload = {
        "doctor_id": 1,
        "session_name": "Past Session",
        "session_date": str(yesterday),
        "start_time": "10:00:00",
        "end_time": "12:00:00",
    }
    resp = client.post(
        "/api/hospitals/1/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 400
    assert "past" in resp.json()["detail"].lower()


def test_create_session_invalid_time_range_returns_400(client: TestClient, staff1_token: str):
    """Start time equal to or later than end time returns 400."""
    tomorrow = date.today() + timedelta(days=1)
    payload = {
        "doctor_id": 1,
        "session_name": "Bad Time Session",
        "session_date": str(tomorrow),
        "start_time": "14:00:00",
        "end_time": "13:00:00",  # earlier than start
    }
    resp = client.post(
        "/api/hospitals/1/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 400
    assert "earlier" in resp.json()["detail"].lower()


def test_create_session_overlapping_time_conflict_409(client: TestClient, staff1_token: str):
    """Scheduling an overlapping session time for the same doctor on the same date returns 409 Conflict."""
    tomorrow = date.today() + timedelta(days=1)
    # Session 1 is already scheduled: Doctor 1, tomorrow, 09:00 - 12:00
    # Overlapping window: 10:30 - 13:30
    payload = {
        "doctor_id": 1,
        "session_name": "Conflicting Cardiology OPD",
        "session_date": str(tomorrow),
        "start_time": "10:30:00",
        "end_time": "13:30:00",
    }
    resp = client.post(
        "/api/hospitals/1/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 409
    assert "overlap" in resp.json()["detail"].lower()


def test_create_session_duplicate_name_conflict_409(client: TestClient, staff1_token: str):
    """Scheduling a session with duplicate name for the same doctor on the same date returns 409 Conflict."""
    tomorrow = date.today() + timedelta(days=1)
    payload = {
        "doctor_id": 1,
        "session_name": "Morning Cardiology OPD",  # Identical to existing session 1
        "session_date": str(tomorrow),
        "start_time": "14:00:00",
        "end_time": "17:00:00",
    }
    resp = client.post(
        "/api/hospitals/1/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


def test_create_session_non_overlapping_succeeds(client: TestClient, staff1_token: str):
    """Scheduling a non-overlapping session for the same doctor on the same date succeeds."""
    tomorrow = date.today() + timedelta(days=1)
    # Session 1 is 09:00 - 12:00. This is 14:00 - 17:00.
    payload = {
        "doctor_id": 1,
        "session_name": "Afternoon Cardiology OPD",
        "session_date": str(tomorrow),
        "start_time": "14:00:00",
        "end_time": "17:00:00",
        "max_capacity": 30,
    }
    resp = client.post(
        "/api/hospitals/1/sessions",
        json=payload,
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["session_name"] == "Afternoon Cardiology OPD"


# ============================================================================
# 7. Session Lifecycle & Status Transition Tests
# ============================================================================

def test_staff_update_session_status_lifecycle(client: TestClient, staff1_token: str):
    """Tests valid lifecycle transitions: SCHEDULED -> ACTIVE -> PAUSED -> COMPLETED."""
    # 1. SCHEDULED -> ACTIVE
    resp1 = client.patch(
        "/api/hospitals/1/sessions/1/status",
        json={"status": "ACTIVE"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["session"]["status"] == "ACTIVE"

    # 2. ACTIVE -> PAUSED
    resp2 = client.patch(
        "/api/hospitals/1/sessions/1/status",
        json={"status": "PAUSED"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["session"]["status"] == "PAUSED"

    # 3. PAUSED -> COMPLETED
    resp3 = client.patch(
        "/api/hospitals/1/sessions/1/status",
        json={"status": "COMPLETED"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp3.status_code == 200
    assert resp3.json()["session"]["status"] == "COMPLETED"


def test_cannot_reopen_completed_session(client: TestClient, staff1_token: str):
    """Verifies that completed sessions cannot be reopened."""
    # First complete session 1
    client.patch(
        "/api/hospitals/1/sessions/1/status",
        json={"status": "COMPLETED"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )

    # Attempt to reopen to ACTIVE
    resp = client.patch(
        "/api/hospitals/1/sessions/1/status",
        json={"status": "ACTIVE"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 409
    assert "completed" in resp.json()["detail"].lower()


def test_invalid_session_status_transition(client: TestClient, staff1_token: str):
    """Verifies that invalid status transitions return 409 Conflict."""
    # Session 1 is SCHEDULED. Attempting an invalid transition or reverting.
    # Activate session 1 first:
    client.patch(
        "/api/hospitals/1/sessions/1/status",
        json={"status": "ACTIVE"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )

    # Attempt ACTIVE -> SCHEDULED (invalid)
    resp = client.patch(
        "/api/hospitals/1/sessions/1/status",
        json={"status": "SCHEDULED"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 409
    assert "invalid session status transition" in resp.json()["detail"].lower()


def test_staff_update_session_status_cross_hospital_forbidden(
    client: TestClient,
    staff1_token: str,
):
    """Staff of Hospital 1 cannot modify session status in Hospital 2."""
    # Session 2 belongs to Hospital 2
    resp = client.patch(
        "/api/hospitals/2/sessions/2/status",
        json={"status": "COMPLETED"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower()


# ============================================================================
# Department & Doctor Creation Tests
# ============================================================================

def test_create_department_success(client: TestClient, staff1_token: str):
    """Staff member of Hospital 1 successfully creates a new clinical department."""
    resp = client.post(
        "/api/hospitals/1/departments",
        json={"name": "Orthopedics", "description": "Bone and joint care"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Orthopedics"
    assert data["hospital_id"] == 1
    assert data["description"] == "Bone and joint care"


def test_create_department_cross_hospital_forbidden(client: TestClient, staff2_token: str):
    """Staff of Hospital 2 cannot create a department in Hospital 1."""
    resp = client.post(
        "/api/hospitals/1/departments",
        json={"name": "Dermatology"},
        headers={"Authorization": f"Bearer {staff2_token}"},
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower()


def test_create_department_patient_forbidden(client: TestClient, patient_token: str):
    """Patients receive 403 Forbidden when attempting to create a department."""
    resp = client.post(
        "/api/hospitals/1/departments",
        json={"name": "Urology"},
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 403


def test_create_department_duplicate_name_rejected(client: TestClient, staff1_token: str):
    """Duplicate department name in the same hospital returns 409 Conflict."""
    # Cardiology is already seeded in Hospital 1
    resp = client.post(
        "/api/hospitals/1/departments",
        json={"name": "Cardiology"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


def test_create_doctor_success(client: TestClient, staff1_token: str):
    """Staff member creates a doctor in their hospital's verified department."""
    resp = client.post(
        "/api/hospitals/1/doctors",
        json={
            "department_id": 1,
            "full_name": "Dr. Kavitha Raman",
            "qualification": "MD, DM",
            "specialization": "Interventional Cardiology",
            "ticket_prefix": "KAV",
            "avg_consultation_time_mins": 20,
        },
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "Dr. Kavitha Raman"
    assert data["hospital_id"] == 1
    assert data["department_id"] == 1
    assert data["ticket_prefix"] == "KAV"
    assert data["is_active"] is True


def test_create_doctor_cross_hospital_forbidden(client: TestClient, staff2_token: str):
    """Staff of Hospital 2 cannot create a doctor in Hospital 1."""
    resp = client.post(
        "/api/hospitals/1/doctors",
        json={
            "department_id": 1,
            "full_name": "Dr. Unauthorized",
            "specialization": "General",
        },
        headers={"Authorization": f"Bearer {staff2_token}"},
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower()


def test_create_doctor_invalid_department_hospital_mismatch(client: TestClient, staff1_token: str):
    """Creating a doctor with a department belonging to another hospital returns 400 Bad Request."""
    # Department 3 belongs to Hospital 2 (Pediatrics), but request targets Hospital 1
    resp = client.post(
        "/api/hospitals/1/doctors",
        json={
            "department_id": 3,
            "full_name": "Dr. Mismatched",
            "specialization": "Pediatrics",
        },
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 400
    assert "does not belong to this hospital" in resp.json()["detail"].lower()


def test_create_department_invalid_name_too_short(client: TestClient, staff1_token: str):
    """Department name shorter than minimum length returns 422 Unprocessable Entity."""
    resp = client.post(
        "/api/hospitals/1/departments",
        json={"name": "A"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 422


def test_create_department_unauthenticated(client: TestClient):
    """Creating a department without authentication returns 401 Unauthorized."""
    resp = client.post(
        "/api/hospitals/1/departments",
        json={"name": "Neurology 2"},
    )
    assert resp.status_code == 401


def test_create_doctor_invalid_name_too_short(client: TestClient, staff1_token: str):
    """Doctor full name shorter than minimum length returns 422 Unprocessable Entity."""
    resp = client.post(
        "/api/hospitals/1/doctors",
        json={
            "department_id": 1,
            "full_name": "D",
            "specialization": "Cardiology",
        },
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 422


def test_create_doctor_nonexistent_department(client: TestClient, staff1_token: str):
    """Specifying a non-existent department returns 404 Not Found."""
    resp = client.post(
        "/api/hospitals/1/doctors",
        json={
            "department_id": 9999,
            "full_name": "Dr. Unlinked",
            "specialization": "Cardiology",
        },
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 404
    assert "department not found" in resp.json()["detail"].lower()


def test_create_doctor_patient_forbidden(client: TestClient, patient_token: str):
    """Patients receive 403 Forbidden when attempting to register a doctor."""
    resp = client.post(
        "/api/hospitals/1/doctors",
        json={
            "department_id": 1,
            "full_name": "Dr. Patient Created",
            "specialization": "General",
        },
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 403


def test_create_doctor_unauthenticated(client: TestClient):
    """Registering a doctor without authentication returns 401 Unauthorized."""
    resp = client.post(
        "/api/hospitals/1/doctors",
        json={
            "department_id": 1,
            "full_name": "Dr. Anon",
            "specialization": "General",
        },
    )
    assert resp.status_code == 401


# ============================================================================
# Consultation Session Creation & Scheduling Tests
# ============================================================================

def test_create_session_success(client: TestClient, staff1_token: str):
    """Staff member of Hospital 1 successfully schedules a new consultation session."""
    target_date = str(date.today() + timedelta(days=2))
    resp = client.post(
        "/api/hospitals/1/sessions",
        json={
            "doctor_id": 1,
            "session_name": "Evening Cardiology Clinic",
            "session_date": target_date,
            "start_time": "16:00:00",
            "end_time": "19:00:00",
            "max_capacity": 25,
        },
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["session_name"] == "Evening Cardiology Clinic"
    assert data["hospital_id"] == 1
    assert data["doctor_id"] == 1
    assert data["status"] == "SCHEDULED"
    assert data["max_capacity"] == 25


def test_create_session_cross_hospital_forbidden(client: TestClient, staff2_token: str):
    """Staff of Hospital 2 cannot schedule a session in Hospital 1."""
    target_date = str(date.today() + timedelta(days=2))
    resp = client.post(
        "/api/hospitals/1/sessions",
        json={
            "doctor_id": 1,
            "session_name": "Unauthorized Clinic",
            "session_date": target_date,
            "start_time": "14:00:00",
            "end_time": "17:00:00",
            "max_capacity": 20,
        },
        headers={"Authorization": f"Bearer {staff2_token}"},
    )
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower()


def test_create_session_patient_forbidden(client: TestClient, patient_token: str):
    """Patients receive 403 Forbidden when attempting to schedule a consultation session."""
    target_date = str(date.today() + timedelta(days=2))
    resp = client.post(
        "/api/hospitals/1/sessions",
        json={
            "doctor_id": 1,
            "session_name": "Patient Scheduled Clinic",
            "session_date": target_date,
            "start_time": "14:00:00",
            "end_time": "17:00:00",
            "max_capacity": 20,
        },
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert resp.status_code == 403


def test_create_session_unauthenticated(client: TestClient):
    """Scheduling a session without authentication returns 401 Unauthorized."""
    target_date = str(date.today() + timedelta(days=2))
    resp = client.post(
        "/api/hospitals/1/sessions",
        json={
            "doctor_id": 1,
            "session_name": "Anonymous Clinic",
            "session_date": target_date,
        },
    )
    assert resp.status_code == 401


def test_create_session_doctor_hospital_mismatch(client: TestClient, staff1_token: str):
    """Scheduling a session in Hospital 1 for a doctor belonging to Hospital 2 returns 404 Not Found."""
    target_date = str(date.today() + timedelta(days=2))
    # Doctor 4 belongs to Hospital 2
    resp = client.post(
        "/api/hospitals/1/sessions",
        json={
            "doctor_id": 4,
            "session_name": "Cross Hospital Doctor Session",
            "session_date": target_date,
            "start_time": "14:00:00",
            "end_time": "17:00:00",
            "max_capacity": 20,
        },
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 404
    assert "doctor not found in this hospital" in resp.json()["detail"].lower()


def test_create_session_invalid_times_rejected(client: TestClient, staff1_token: str):
    """Scheduling a session where start_time >= end_time returns 400 Bad Request."""
    target_date = str(date.today() + timedelta(days=2))
    resp = client.post(
        "/api/hospitals/1/sessions",
        json={
            "doctor_id": 1,
            "session_name": "Inverted Time Session",
            "session_date": target_date,
            "start_time": "17:00:00",
            "end_time": "14:00:00",
            "max_capacity": 20,
        },
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 400
    assert "earlier than end_time" in resp.json()["detail"]
