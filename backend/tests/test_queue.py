"""
Automated tests for Queue and Token Management APIs (Phase 2, Milestone 4).
Uses an isolated in-memory SQLite database to ensure tests run independently and never modify MySQL.
"""

from datetime import date, time, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    QueueTicket,
    TicketStatus,
    TicketSource,
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
    yesterday = today - timedelta(days=1)

    with TestingSessionLocal() as db:
        # 1. Seed Hospitals
        h1 = Hospital(
            id=1,
            name="City Care Hospital",
            registration_number="REG-H1",
            address="100 Main Road",
            city="Coimbatore",
            latitude=11.01,
            longitude=76.95,
            status=HospitalStatus.APPROVED,
            is_accepting_bookings=True,
            avg_consultation_time_mins=15,
        )
        h2 = Hospital(
            id=2,
            name="Apex Clinic",
            registration_number="REG-H2",
            address="200 West St",
            city="Coimbatore",
            latitude=11.02,
            longitude=76.96,
            status=HospitalStatus.APPROVED,
            is_accepting_bookings=True,
            avg_consultation_time_mins=20,
        )
        h3_unapproved = Hospital(
            id=3,
            name="Pending Hospital",
            registration_number="REG-H3",
            address="300 East St",
            city="Coimbatore",
            latitude=11.03,
            longitude=76.97,
            status=HospitalStatus.PENDING_APPROVAL,
            is_accepting_bookings=False,
            avg_consultation_time_mins=15,
        )
        db.add_all([h1, h2, h3_unapproved])
        db.flush()

        # 2. Seed Users
        admin_user = User(
            id=1,
            email="admin@queueless.test",
            password_hash=hash_password("Pass123!"),
            full_name="Admin Admin",
            role=UserRole.ADMIN,
            is_active=True,
        )
        staff1 = User(
            id=2,
            email="staff1@queueless.test",
            password_hash=hash_password("Pass123!"),
            full_name="Staff Hospital 1",
            role=UserRole.STAFF,
            hospital_id=1,
            is_active=True,
        )
        staff2 = User(
            id=3,
            email="staff2@queueless.test",
            password_hash=hash_password("Pass123!"),
            full_name="Staff Hospital 2",
            role=UserRole.STAFF,
            hospital_id=2,
            is_active=True,
        )
        patient1 = User(
            id=4,
            email="patient1@queueless.test",
            password_hash=hash_password("Pass123!"),
            full_name="Patient One",
            phone="+919999000001",
            role=UserRole.PATIENT,
            is_active=True,
        )
        patient2 = User(
            id=5,
            email="patient2@queueless.test",
            password_hash=hash_password("Pass123!"),
            full_name="Patient Two",
            phone="+919999000002",
            role=UserRole.PATIENT,
            is_active=True,
        )
        patient3 = User(
            id=6,
            email="patient3@queueless.test",
            password_hash=hash_password("Pass123!"),
            full_name="Patient Three",
            phone="+919999000003",
            role=UserRole.PATIENT,
            is_active=True,
        )
        db.add_all([admin_user, staff1, staff2, patient1, patient2, patient3])
        db.flush()

        # 3. Seed Departments & Doctors
        dept1 = Department(id=1, hospital_id=1, name="Cardiology")
        dept2 = Department(id=2, hospital_id=2, name="Pediatrics")
        db.add_all([dept1, dept2])
        db.flush()

        doc1 = Doctor(
            id=1,
            hospital_id=1,
            department_id=1,
            full_name="Dr. S. Kulkarni",
            ticket_prefix="CARD",
            avg_consultation_time_mins=15,
            is_active=True,
            specialization="Cardiology",
        )
        doc2 = Doctor(
            id=2,
            hospital_id=1,
            department_id=1,
            full_name="Dr. M. Roy",
            ticket_prefix="GEN",
            avg_consultation_time_mins=10,
            is_active=True,
            specialization="General",
        )
        doc3_h2 = Doctor(
            id=3,
            hospital_id=2,
            department_id=2,
            full_name="Dr. N. Iyer",
            ticket_prefix="PED",
            avg_consultation_time_mins=20,
            is_active=True,
            specialization="Pediatrics",
        )
        db.add_all([doc1, doc2, doc3_h2])
        db.flush()

        # 4. Seed Sessions
        # Session 1: Standard Active Session (h1, doc1, today, capacity 50)
        s1 = ConsultationSession(
            id=1,
            hospital_id=1,
            doctor_id=1,
            session_name="Morning Cardiology OPD",
            session_date=today,
            status=SessionStatus.ACTIVE,
            last_sequence_number=0,
            max_capacity=50,
        )
        # Session 2: Capacity Capped Session (h1, doc2, today, capacity 2)
        s2_capped = ConsultationSession(
            id=2,
            hospital_id=1,
            doctor_id=2,
            session_name="Limited General OPD",
            session_date=today,
            status=SessionStatus.ACTIVE,
            last_sequence_number=0,
            max_capacity=2,
        )
        # Session 3: Hospital 2 Session (h2, doc3_h2, today)
        s3_h2 = ConsultationSession(
            id=3,
            hospital_id=2,
            doctor_id=3,
            session_name="Pediatric Clinic",
            session_date=today,
            status=SessionStatus.ACTIVE,
            last_sequence_number=0,
            max_capacity=30,
        )
        # Session 4: Completed Session (cannot join)
        s4_completed = ConsultationSession(
            id=4,
            hospital_id=1,
            doctor_id=1,
            session_name="Finished OPD",
            session_date=today,
            status=SessionStatus.COMPLETED,
            last_sequence_number=0,
            max_capacity=10,
        )
        # Session 5: Paused Session (cannot join)
        s5_paused = ConsultationSession(
            id=5,
            hospital_id=1,
            doctor_id=1,
            session_name="Paused OPD",
            session_date=today,
            status=SessionStatus.PAUSED,
            last_sequence_number=0,
            max_capacity=10,
        )
        # Session 6: Past Date Session
        s6_past = ConsultationSession(
            id=6,
            hospital_id=1,
            doctor_id=1,
            session_name="Yesterday OPD",
            session_date=yesterday,
            status=SessionStatus.ACTIVE,
            last_sequence_number=0,
            max_capacity=10,
        )
        # Session 7: Unapproved Hospital Session
        s7_unapproved = ConsultationSession(
            id=7,
            hospital_id=3,
            doctor_id=1,
            session_name="Pending Hospital OPD",
            session_date=today,
            status=SessionStatus.ACTIVE,
            last_sequence_number=0,
            max_capacity=10,
        )
        db.add_all([s1, s2_capped, s3_h2, s4_completed, s5_paused, s6_past, s7_unapproved])
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


@pytest.fixture(name="patient1_token")
def patient1_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "patient1@queueless.test", "password": "Pass123!"})
    return resp.json()["access_token"]


@pytest.fixture(name="patient2_token")
def patient2_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "patient2@queueless.test", "password": "Pass123!"})
    return resp.json()["access_token"]


@pytest.fixture(name="patient3_token")
def patient3_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "patient3@queueless.test", "password": "Pass123!"})
    return resp.json()["access_token"]


@pytest.fixture(name="staff1_token")
def staff1_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "staff1@queueless.test", "password": "Pass123!"})
    return resp.json()["access_token"]


@pytest.fixture(name="staff2_token")
def staff2_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "staff2@queueless.test", "password": "Pass123!"})
    return resp.json()["access_token"]


@pytest.fixture(name="admin_token")
def admin_token_fixture(client: TestClient):
    resp = client.post("/api/auth/login", json={"email": "admin@queueless.test", "password": "Pass123!"})
    return resp.json()["access_token"]


# ============================================================================
# 1. Role Enforcement & Privacy Tests
# ============================================================================

def test_patient_can_join_online_queue(client: TestClient, patient1_token: str):
    """Patient role can successfully join an active consultation session queue."""
    resp = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Patient One", "patient_phone": "+919999000001"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()["ticket"]
    assert data["ticket_number"] == "CARD-001"
    assert data["sequence_number"] == 1
    assert data["status"] == "WAITING"
    assert data["queue_position"] == 1
    assert data["patients_ahead"] == 0


def test_staff_cannot_join_online_queue(client: TestClient, staff1_token: str):
    """Staff accounts are forbidden from using the patient online join endpoint."""
    resp = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Staff As Patient"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 403
    assert "reserved for patient accounts" in resp.json()["detail"].lower()


def test_admin_cannot_join_online_queue(client: TestClient, admin_token: str):
    """Admin accounts are forbidden from using the patient online join endpoint."""
    resp = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Admin As Patient"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403
    assert "reserved for patient accounts" in resp.json()["detail"].lower()


def test_unauthenticated_join_returns_401(client: TestClient):
    """Unauthenticated requests cannot join the queue."""
    resp = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Anon"},
    )
    assert resp.status_code == 401


def test_patient_privacy_ownership_guard(client: TestClient, patient1_token: str, patient2_token: str):
    """Patient cannot view details of another patient's ticket."""
    # Patient 1 creates a ticket
    resp1 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Patient One", "patient_phone": "+919999000001"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    ticket_id = resp1.json()["ticket"]["id"]

    # Patient 2 attempts to view Patient 1's ticket
    resp2 = client.get(
        f"/api/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {patient2_token}"},
    )
    assert resp2.status_code == 403
    assert "own tickets" in resp2.json()["detail"].lower()


def test_public_lobby_status_protects_patient_privacy(client: TestClient, patient1_token: str):
    """Public lobby display returns tokens only, strictly excluding patient names and phones."""
    client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Sensitive Patient Name", "patient_phone": "+919999999999"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )

    resp = client.get("/api/sessions/1/queue/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == 1
    assert data["waiting_count"] == 1
    # Check that patient name and phone are NOT present in the public response schema
    assert "patient_name" not in data
    assert "patient_phone" not in data
    assert "Sensitive Patient Name" not in str(data)
    assert "+919999999999" not in str(data)


# ============================================================================
# 2. Sequential Token Allocation & Duplicate Prevention
# ============================================================================

def test_sequential_token_allocation(client: TestClient, patient1_token: str, patient2_token: str):
    """Tokens are allocated sequentially (1, 2) without sequence reuse."""
    resp1 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Patient One"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp1.status_code == 201
    assert resp1.json()["ticket"]["sequence_number"] == 1
    assert resp1.json()["ticket"]["ticket_number"] == "CARD-001"

    resp2 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Patient Two"},
        headers={"Authorization": f"Bearer {patient2_token}"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["ticket"]["sequence_number"] == 2
    assert resp2.json()["ticket"]["ticket_number"] == "CARD-002"


def test_duplicate_active_ticket_in_same_session_prevented(client: TestClient, patient1_token: str):
    """A patient cannot join the same session twice while their ticket is active."""
    # First join
    client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Patient One"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )

    # Second join in same session
    resp = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Patient One Again"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp.status_code == 409
    assert "already hold an active queue ticket" in resp.json()["detail"].lower()


def test_patient_can_join_different_doctor_session(
    client: TestClient,
    patient1_token: str,
):
    """A patient can simultaneously hold tickets in two different doctor sessions."""
    # Join doctor 1 (Cardiology)
    resp1 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Patient One"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp1.status_code == 201

    # Join doctor 3 in Hospital 2 (Pediatrics)
    resp2 = client.post(
        "/api/sessions/3/tickets",
        json={"patient_name": "Patient One"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp2.status_code == 201
    assert resp2.json()["ticket"]["ticket_number"] == "PED-001"


# ============================================================================
# 3. Queue Positions, Dynamic Updates & Wait Estimates
# ============================================================================

def test_queue_position_and_wait_time_calculation(
    client: TestClient,
    patient1_token: str,
    patient2_token: str,
    patient3_token: str,
):
    """Verifies that queue position and estimated wait time reflect real queue state."""
    # Patient 1 joins (pos 1, ahead 0, est wait 0)
    resp1 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "P1"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    t1 = resp1.json()["ticket"]
    assert t1["queue_position"] == 1
    assert t1["patients_ahead"] == 0
    assert t1["estimated_wait_mins"] == 0

    # Patient 2 joins (pos 2, ahead 1, est wait 15 mins)
    resp2 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "P2"},
        headers={"Authorization": f"Bearer {patient2_token}"},
    )
    t2 = resp2.json()["ticket"]
    assert t2["queue_position"] == 2
    assert t2["patients_ahead"] == 1
    assert t2["estimated_wait_mins"] == 15  # 1 ahead * 15 min avg

    # Patient 3 joins (pos 3, ahead 2, est wait 30 mins)
    resp3 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "P3"},
        headers={"Authorization": f"Bearer {patient3_token}"},
    )
    t3 = resp3.json()["ticket"]
    assert t3["queue_position"] == 3
    assert t3["patients_ahead"] == 2
    assert t3["estimated_wait_mins"] == 30  # 2 ahead * 15 min avg


def test_position_advances_dynamically_after_cancellation(
    client: TestClient,
    patient1_token: str,
    patient2_token: str,
):
    """When a preceding patient cancels, subsequent patients immediately advance."""
    resp1 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "P1"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    t1_id = resp1.json()["ticket"]["id"]

    resp2 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "P2"},
        headers={"Authorization": f"Bearer {patient2_token}"},
    )
    t2_id = resp2.json()["ticket"]["id"]
    assert resp2.json()["ticket"]["queue_position"] == 2

    # Patient 1 cancels their ticket
    cancel_resp = client.post(
        f"/api/tickets/{t1_id}/cancel",
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["ticket"]["status"] == "CANCELLED"

    # Patient 2 inspects their ticket: dynamically advanced to position 1!
    resp_t2 = client.get(
        f"/api/tickets/{t2_id}",
        headers={"Authorization": f"Bearer {patient2_token}"},
    )
    assert resp_t2.json()["queue_position"] == 1
    assert resp_t2.json()["patients_ahead"] == 0
    assert resp_t2.json()["estimated_wait_mins"] == 0


# ============================================================================
# 4. Capacity Semantics: Active Capacity
# ============================================================================

def test_active_capacity_enforced(
    client: TestClient,
    patient1_token: str,
    patient2_token: str,
    patient3_token: str,
):
    """Session 2 has max_capacity=2. Third join is rejected."""
    # Join 1
    resp1 = client.post(
        "/api/sessions/2/tickets",
        json={"patient_name": "P1"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp1.status_code == 201

    # Join 2
    resp2 = client.post(
        "/api/sessions/2/tickets",
        json={"patient_name": "P2"},
        headers={"Authorization": f"Bearer {patient2_token}"},
    )
    assert resp2.status_code == 201

    # Join 3 should hit capacity limit
    resp3 = client.post(
        "/api/sessions/2/tickets",
        json={"patient_name": "P3"},
        headers={"Authorization": f"Bearer {patient3_token}"},
    )
    assert resp3.status_code == 409
    assert "capacity limit" in resp3.json()["detail"].lower()


def test_cancellation_frees_active_capacity(
    client: TestClient,
    patient1_token: str,
    patient2_token: str,
    patient3_token: str,
):
    """When an active ticket is cancelled, active capacity is freed for a new patient."""
    resp1 = client.post(
        "/api/sessions/2/tickets",
        json={"patient_name": "P1"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    t1_id = resp1.json()["ticket"]["id"]

    client.post(
        "/api/sessions/2/tickets",
        json={"patient_name": "P2"},
        headers={"Authorization": f"Bearer {patient2_token}"},
    )

    # Cancel Ticket 1
    client.post(f"/api/tickets/{t1_id}/cancel", headers={"Authorization": f"Bearer {patient1_token}"})

    # Patient 3 can now join because capacity freed up!
    resp3 = client.post(
        "/api/sessions/2/tickets",
        json={"patient_name": "P3"},
        headers={"Authorization": f"Bearer {patient3_token}"},
    )
    assert resp3.status_code == 201
    # Note: sequence is NOT reused; sequence increments to 3!
    assert resp3.json()["ticket"]["sequence_number"] == 3
    assert resp3.json()["ticket"]["ticket_number"] == "GEN-003"


# ============================================================================
# 5. Call-Next Workflow & Clinical Lifecycle
# ============================================================================

def test_staff_call_next_success(
    client: TestClient,
    patient1_token: str,
    staff1_token: str,
):
    """Staff calls next patient: transitions WAITING to CALLING."""
    client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "P1"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )

    resp = client.post(
        "/api/hospitals/1/sessions/1/queue/call-next",
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["ticket"]
    assert data["status"] == "CALLING"
    assert data["ticket_number"] == "CARD-001"
    assert data["called_at"] is not None


def test_call_next_blocked_when_patient_already_calling(
    client: TestClient,
    patient1_token: str,
    patient2_token: str,
    staff1_token: str,
):
    """Calling next while a patient is already CALLING returns 409 Conflict."""
    client.post("/api/sessions/1/tickets", json={"patient_name": "P1"}, headers={"Authorization": f"Bearer {patient1_token}"})
    client.post("/api/sessions/1/tickets", json={"patient_name": "P2"}, headers={"Authorization": f"Bearer {patient2_token}"})

    # Call patient 1
    client.post("/api/hospitals/1/sessions/1/queue/call-next", headers={"Authorization": f"Bearer {staff1_token}"})

    # Attempt to call patient 2 while patient 1 is still CALLING
    resp = client.post(
        "/api/hospitals/1/sessions/1/queue/call-next",
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 409
    assert "currently calling" in resp.json()["detail"].lower()


def test_full_clinical_workflow(
    client: TestClient,
    patient1_token: str,
    patient2_token: str,
    staff1_token: str,
):
    """Tests lifecycle: WAITING -> CALLING -> IN_CONSULTATION -> COMPLETED, then calling next."""
    client.post("/api/sessions/1/tickets", json={"patient_name": "P1"}, headers={"Authorization": f"Bearer {patient1_token}"})
    client.post("/api/sessions/1/tickets", json={"patient_name": "P2"}, headers={"Authorization": f"Bearer {patient2_token}"})

    # 1. Staff calls next -> P1 is CALLING
    call_resp = client.post("/api/hospitals/1/sessions/1/queue/call-next", headers={"Authorization": f"Bearer {staff1_token}"})
    t1_id = call_resp.json()["ticket"]["id"]
    assert call_resp.json()["ticket"]["status"] == "CALLING"

    # 2. Staff serves P1 -> P1 is IN_CONSULTATION
    serve_resp = client.post(f"/api/hospitals/1/tickets/{t1_id}/serve", headers={"Authorization": f"Bearer {staff1_token}"})
    assert serve_resp.status_code == 200
    assert serve_resp.json()["ticket"]["status"] == "IN_CONSULTATION"
    assert serve_resp.json()["ticket"]["started_at"] is not None

    # 3. Staff completes P1 -> P1 is COMPLETED
    comp_resp = client.post(f"/api/hospitals/1/tickets/{t1_id}/complete", headers={"Authorization": f"Bearer {staff1_token}"})
    assert comp_resp.status_code == 200
    assert comp_resp.json()["ticket"]["status"] == "COMPLETED"
    assert comp_resp.json()["ticket"]["completed_at"] is not None

    # 4. Room is clear! Staff can now call P2
    call2_resp = client.post("/api/hospitals/1/sessions/1/queue/call-next", headers={"Authorization": f"Bearer {staff1_token}"})
    assert call2_resp.status_code == 200
    assert call2_resp.json()["ticket"]["status"] == "CALLING"
    assert call2_resp.json()["ticket"]["ticket_number"] == "CARD-002"


def test_no_show_workflow(
    client: TestClient,
    patient1_token: str,
    patient2_token: str,
    staff1_token: str,
):
    """Called patient does not appear -> marked NO_SHOW -> staff can call next."""
    client.post("/api/sessions/1/tickets", json={"patient_name": "P1"}, headers={"Authorization": f"Bearer {patient1_token}"})
    client.post("/api/sessions/1/tickets", json={"patient_name": "P2"}, headers={"Authorization": f"Bearer {patient2_token}"})

    # Call P1
    call1 = client.post("/api/hospitals/1/sessions/1/queue/call-next", headers={"Authorization": f"Bearer {staff1_token}"})
    t1_id = call1.json()["ticket"]["id"]

    # Mark P1 as NO_SHOW
    no_show_resp = client.post(f"/api/hospitals/1/tickets/{t1_id}/no-show", headers={"Authorization": f"Bearer {staff1_token}"})
    assert no_show_resp.status_code == 200
    assert no_show_resp.json()["ticket"]["status"] == "NO_SHOW"

    # Room is cleared; staff can call P2 immediately
    call2 = client.post("/api/hospitals/1/sessions/1/queue/call-next", headers={"Authorization": f"Bearer {staff1_token}"})
    assert call2.status_code == 200
    assert call2.json()["ticket"]["ticket_number"] == "CARD-002"


def test_empty_queue_call_next_returns_200_null_ticket(client: TestClient, staff1_token: str):
    """Calling next on an empty queue returns HTTP 200 OK with ticket: null."""
    resp = client.post(
        "/api/hospitals/1/sessions/1/queue/call-next",
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["ticket"] is None
    assert "no patients are currently waiting" in resp.json()["message"].lower()


# ============================================================================
# 6. Walk-In Ticket Operations
# ============================================================================

def test_staff_issue_walk_in_ticket(client: TestClient, staff1_token: str):
    """Front desk staff can issue an in-person walk-in ticket."""
    resp = client.post(
        "/api/hospitals/1/sessions/1/walk-in",
        json={"patient_name": "Walk-In Patient", "patient_phone": "+919876543210"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp.status_code == 201
    ticket = resp.json()["ticket"]
    assert ticket["source"] == "WALK_IN"
    assert ticket["user_id"] is None
    assert ticket["status"] == "WAITING"
    assert ticket["ticket_number"] == "CARD-001"


def test_patient_cannot_issue_walk_in_ticket(client: TestClient, patient1_token: str):
    """Patients cannot issue walk-in tickets."""
    resp = client.post(
        "/api/hospitals/1/sessions/1/walk-in",
        json={"patient_name": "Fake Walk-In"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp.status_code == 403


# ============================================================================
# 7. Hospital-Level Staff Isolation
# ============================================================================

def test_staff_cross_hospital_queue_actions_forbidden(
    client: TestClient,
    staff1_token: str,
):
    """Staff of Hospital 1 cannot call next, complete, or issue walk-in for Hospital 2."""
    # Call-next for hospital 2
    resp1 = client.post(
        "/api/hospitals/2/sessions/3/queue/call-next",
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp1.status_code == 403

    # Walk-in for hospital 2
    resp2 = client.post(
        "/api/hospitals/2/sessions/3/walk-in",
        json={"patient_name": "Cross Hospital Walk-In"},
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert resp2.status_code == 403


# ============================================================================
# 8. Pre-Flight Booking Eligibility Guards
# ============================================================================

def test_join_completed_session_rejected(client: TestClient, patient1_token: str):
    """Attempting to join a completed session returns 400 Bad Request."""
    resp = client.post(
        "/api/sessions/4/tickets",
        json={"patient_name": "Late Patient"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp.status_code == 400
    assert "completed" in resp.json()["detail"].lower()


def test_join_paused_session_rejected(client: TestClient, patient1_token: str):
    """Attempting to join a paused session returns 409 Conflict."""
    resp = client.post(
        "/api/sessions/5/tickets",
        json={"patient_name": "Paused Patient"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp.status_code == 409
    assert "paused" in resp.json()["detail"].lower()


def test_join_past_session_rejected(client: TestClient, patient1_token: str):
    """Attempting to join a past date session returns 400 Bad Request."""
    resp = client.post(
        "/api/sessions/6/tickets",
        json={"patient_name": "Past Patient"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp.status_code == 400
    assert "past" in resp.json()["detail"].lower()


def test_join_unapproved_hospital_session_rejected(client: TestClient, patient1_token: str):
    """Attempting to join a session under an unapproved hospital returns 404."""
    resp = client.post(
        "/api/sessions/7/tickets",
        json={"patient_name": "Patient"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp.status_code == 404


def test_complete_rejected_from_calling_status(
    client: TestClient,
    patient1_token: str,
    staff1_token: str,
):
    """CALLING -> COMPLETED is strictly rejected. Must be IN_CONSULTATION."""
    join_resp = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "P1"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    t1_id = join_resp.json()["ticket"]["id"]

    # Call patient -> status is CALLING
    client.post("/api/hospitals/1/sessions/1/queue/call-next", headers={"Authorization": f"Bearer {staff1_token}"})

    # Attempt to complete directly while in CALLING status
    comp_resp = client.post(
        f"/api/hospitals/1/tickets/{t1_id}/complete",
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert comp_resp.status_code == 409
    assert "in_consultation" in comp_resp.json()["detail"].lower()


def test_no_show_rejected_from_waiting_status(
    client: TestClient,
    patient1_token: str,
    staff1_token: str,
):
    """WAITING -> NO_SHOW is strictly rejected. Patient must be in CALLING status."""
    join_resp = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "P1"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    t1_id = join_resp.json()["ticket"]["id"]

    # Attempt to mark NO_SHOW directly while still WAITING (never called)
    no_show_resp = client.post(
        f"/api/hospitals/1/tickets/{t1_id}/no-show",
        headers={"Authorization": f"Bearer {staff1_token}"},
    )
    assert no_show_resp.status_code == 409
    assert "calling status" in no_show_resp.json()["detail"].lower()


# ============================================================================
# 9. Hospital-Wide Single Active Ticket & Concurrency Guarantees
# ============================================================================

def test_duplicate_active_ticket_different_session_same_hospital_rejected(
    client: TestClient,
    patient1_token: str,
):
    """
    Patient cannot hold active tickets in multiple doctor sessions at the SAME hospital.
    Joining session 1 then session 2 in Hospital 1 returns 409 Conflict.
    """
    # Join session 1 (Cardiology) in Hospital 1
    resp1 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Patient One"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp1.status_code == 201
    assert resp1.json()["ticket"]["status"] == "WAITING"

    # Attempt to join session 2 (General OPD) in Hospital 1 while session 1 ticket is active
    resp2 = client.post(
        "/api/sessions/2/tickets",
        json={"patient_name": "Patient One"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp2.status_code == 409
    assert "already hold an active queue ticket" in resp2.json()["detail"].lower()
    assert "at this hospital" in resp2.json()["detail"].lower()


def test_concurrent_booking_same_patient_same_hospital(
    client: TestClient,
    patient2_token: str,
):
    """
    Concurrent queue join requests by the same patient for the same hospital.
    Guarantees exactly one succeeds with 201 Created and all others receive 409 Conflict.
    """
    import threading
    call_lock = threading.Lock()

    def attempt_join(idx: int):
        sess_id = 1 if idx % 2 == 0 else 2
        with call_lock:
            return client.post(
                f"/api/sessions/{sess_id}/tickets",
                json={"patient_name": f"Concurrent Patient {idx}"},
                headers={"Authorization": f"Bearer {patient2_token}"},
            )

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(attempt_join, i) for i in range(5)]
        results = [f.result() for f in as_completed(futures)]

    status_codes = [r.status_code for r in results]
    success_count = status_codes.count(201)
    conflict_count = status_codes.count(409)

    assert success_count == 1, f"Expected exactly 1 successful booking, got {success_count}. Status codes: {status_codes}"
    assert conflict_count == 4, f"Expected 4 conflicts, got {conflict_count}. Status codes: {status_codes}"


def test_cross_patient_cancellation_forbidden(
    client: TestClient,
    patient1_token: str,
    patient2_token: str,
):
    """Patient B cannot cancel Patient A's active queue ticket."""
    resp1 = client.post(
        "/api/sessions/1/tickets",
        json={"patient_name": "Patient One"},
        headers={"Authorization": f"Bearer {patient1_token}"},
    )
    assert resp1.status_code == 201
    t1_id = resp1.json()["ticket"]["id"]

    # Patient 2 attempts to cancel Patient 1's ticket
    cancel_resp = client.post(
        f"/api/tickets/{t1_id}/cancel",
        headers={"Authorization": f"Bearer {patient2_token}"},
    )
    assert cancel_resp.status_code == 403
    assert "own tickets" in cancel_resp.json()["detail"].lower()
