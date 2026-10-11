"""
Unit tests for SQLAlchemy models structure and integrity.
Uses an in-memory SQLite database to verify table definitions,
relationships, and constraints without requiring an external MySQL connection.
"""

from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import (
    Hospital,
    Department,
    Doctor,
    ConsultationSession,
    User,
    QueueTicket,
    HospitalStatus,
    UserRole,
    SessionStatus,
    TicketSource,
    TicketStatus,
)


def test_models_table_creation():
    """Verify that all ORM tables compile and create successfully without foreign key or syntax errors."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)

    table_names = Base.metadata.tables.keys()
    assert "hospitals" in table_names
    assert "departments" in table_names
    assert "doctors" in table_names
    assert "consultation_sessions" in table_names
    assert "users" in table_names
    assert "queue_tickets" in table_names


def test_models_relationships():
    """Verify that relationships between Hospital, Department, Doctor, Session, and QueueTicket function correctly."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)
    session = TestingSession()

    # 1. Create Hospital
    hospital = Hospital(
        name="[Demo] Test Hospital",
        registration_number="TEST-001",
        address="123 Test St",
        latitude=11.0,
        longitude=76.9,
        status=HospitalStatus.APPROVED,
        is_accepting_bookings=True,
    )
    session.add(hospital)
    session.commit()
    assert hospital.id is not None

    # 2. Add Department
    dept = Department(hospital_id=hospital.id, name="Test Department")
    session.add(dept)
    session.commit()

    # 3. Add Doctor
    doctor = Doctor(
        hospital_id=hospital.id,
        department_id=dept.id,
        full_name="Dr. Test",
        specialization="General",
        ticket_prefix="TST",
    )
    session.add(doctor)
    session.commit()

    # 4. Add Session
    consult_session = ConsultationSession(
        hospital_id=hospital.id,
        doctor_id=doctor.id,
        session_name="Morning OPD",
        session_date=date.today(),
        status=SessionStatus.ACTIVE,
    )
    session.add(consult_session)
    session.commit()

    # 5. Add Ticket
    ticket = QueueTicket(
        session_id=consult_session.id,
        hospital_id=hospital.id,
        doctor_id=doctor.id,
        ticket_number="TST-001",
        sequence_number=1,
        patient_name="John Doe",
        source=TicketSource.ONLINE,
        status=TicketStatus.WAITING,
    )
    session.add(ticket)
    session.commit()

    # Verify back-references
    assert len(hospital.departments) == 1
    assert len(hospital.doctors) == 1
    assert len(hospital.sessions) == 1
    assert len(consult_session.tickets) == 1
    assert ticket.doctor.full_name == "Dr. Test"

    session.close()
