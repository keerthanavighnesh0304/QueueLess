"""
QueueLess Safe Database Initialization & Seed Script

This script:
1. Creates all database tables if they do not exist.
2. Creates an initial platform administrator safely (using environment variables or secure prompts).
3. Seeds clearly labeled fictional demonstration hospitals, departments, doctors, and active sessions.
4. Seeds sample staff and patient accounts for testing.
"""

import os
import sys
from datetime import date, time
import bcrypt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, SessionLocal, Base
from app.models import (
    Hospital,
    Department,
    Doctor,
    ConsultationSession,
    User,
    QueueTicket,
    UserRole,
    HospitalStatus,
    SessionStatus,
)


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt with a secure salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def validate_seed_credentials() -> tuple[str, str]:
    """
    Validates that required credentials are non-empty before touching the database.
    Stops execution immediately if either credential is missing or blank.
    """
    admin_password = os.getenv("ADMIN_INITIAL_PASSWORD", settings.ADMIN_INITIAL_PASSWORD)
    demo_password = os.getenv("DEMO_ACCOUNTS_PASSWORD", settings.DEMO_ACCOUNTS_PASSWORD)

    missing = []
    if not admin_password or not admin_password.strip():
        missing.append("ADMIN_INITIAL_PASSWORD")
    if not demo_password or not demo_password.strip():
        missing.append("DEMO_ACCOUNTS_PASSWORD")

    if missing:
        print("\n" + "=" * 60)
        print("[ERROR] Required seed credential(s) missing or empty in backend/.env:")
        for var in missing:
            print(f"  • {var}")
        print("\nPlease configure these settings in backend/.env before running the seed script.")
        print("=" * 60 + "\n")
        sys.exit(1)

    return admin_password.strip(), demo_password.strip()


def get_or_create_admin(db: Session, admin_password: str) -> User:
    """Safely retrieves or provisions the initial administrator account."""
    admin_email = os.getenv("ADMIN_EMAIL", settings.ADMIN_EMAIL)
    existing_admin = db.query(User).filter(User.email == admin_email).first()

    if existing_admin:
        print(f"[INFO] Admin account '{admin_email}' already exists. Skipping creation.")
        return existing_admin

    admin = User(
        email=admin_email,
        password_hash=hash_password(admin_password),
        full_name=settings.ADMIN_FULL_NAME,
        phone="+919876543210",
        role=UserRole.ADMIN,
        hospital_id=None,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"[SUCCESS] Admin account created: {admin_email}")
    return admin


def seed_demo_data(db: Session, demo_password: str) -> None:
    """Seeds fictional demonstration healthcare facilities and accounts."""
    # Check if demo hospitals are already present
    demo_count = db.query(Hospital).filter(Hospital.registration_number == "DEMO-HOSP-001").count()
    if demo_count > 0:
        print("[INFO] Fictional demonstration data is already seeded. Skipping.")
        return

    print("[INFO] Seeding fictional demo healthcare data (Coimbatore test set)...")

    # 1. Approved Hospital: City Care Hospital
    h1 = Hospital(
        name="[Demo] City Care Hospital",
        registration_number="DEMO-HOSP-001",
        address="124 Cross Cut Road, Gandhipuram",
        city="Coimbatore",
        latitude=11.016844,
        longitude=76.955832,
        status=HospitalStatus.APPROVED,
        is_accepting_bookings=True,
        avg_consultation_time_mins=15,
    )

    # 2. Approved Hospital: Green Life Clinic
    h2 = Hospital(
        name="[Demo] Green Life Clinic",
        registration_number="DEMO-HOSP-002",
        address="45 DB Road, RS Puram",
        city="Coimbatore",
        latitude=11.008920,
        longitude=76.942710,
        status=HospitalStatus.APPROVED,
        is_accepting_bookings=True,
        avg_consultation_time_mins=10,
    )

    # 3. Pending Hospital: Sunrise Medical Center (For testing admin approval flow)
    h3 = Hospital(
        name="[Demo] Sunrise Medical Center",
        registration_number="DEMO-HOSP-003",
        address="88 Avinashi Road, Peelamedu",
        city="Coimbatore",
        latitude=11.028010,
        longitude=77.005020,
        status=HospitalStatus.PENDING_APPROVAL,
        is_accepting_bookings=False,
        avg_consultation_time_mins=20,
    )

    db.add_all([h1, h2, h3])
    db.flush()

    # Departments for Hospital 1
    d1_gen = Department(hospital_id=h1.id, name="General Medicine", description="Primary care & diagnosis")
    d1_ped = Department(hospital_id=h1.id, name="Pediatrics", description="Child health & immunization")
    # Department for Hospital 2
    d2_card = Department(hospital_id=h2.id, name="Cardiology", description="Heart & vascular consultations")

    db.add_all([d1_gen, d1_ped, d2_card])
    db.flush()

    # Doctors
    doc1 = Doctor(
        hospital_id=h1.id,
        department_id=d1_gen.id,
        full_name="Dr. A. Sharma, MBBS, MD",
        qualification="MD - General Medicine",
        specialization="Internal Medicine",
        ticket_prefix="GEN",
        avg_consultation_time_mins=15,
        is_active=True,
    )
    doc2 = Doctor(
        hospital_id=h1.id,
        department_id=d1_ped.id,
        full_name="Dr. R. Priya, DCH",
        qualification="MBBS, DCH",
        specialization="Pediatrics",
        ticket_prefix="PED",
        avg_consultation_time_mins=12,
        is_active=True,
    )
    doc3 = Doctor(
        hospital_id=h2.id,
        department_id=d2_card.id,
        full_name="Dr. K. Anand, DM",
        qualification="MD, DM (Cardiology)",
        specialization="Cardiology",
        ticket_prefix="CARD",
        avg_consultation_time_mins=20,
        is_active=True,
    )

    db.add_all([doc1, doc2, doc3])
    db.flush()

    # Active Consultation Sessions for Today
    today = date.today()
    sess1 = ConsultationSession(
        hospital_id=h1.id,
        doctor_id=doc1.id,
        session_name="Morning General OPD",
        session_date=today,
        start_time=time(9, 0),
        end_time=time(13, 0),
        status=SessionStatus.ACTIVE,
        last_sequence_number=0,
        max_capacity=50,
    )
    sess2 = ConsultationSession(
        hospital_id=h1.id,
        doctor_id=doc2.id,
        session_name="Morning Pediatric OPD",
        session_date=today,
        start_time=time(9, 30),
        end_time=time(13, 30),
        status=SessionStatus.ACTIVE,
        last_sequence_number=0,
        max_capacity=40,
    )
    sess3 = ConsultationSession(
        hospital_id=h2.id,
        doctor_id=doc3.id,
        session_name="Cardiology Specialist Clinic",
        session_date=today,
        start_time=time(10, 0),
        end_time=time(14, 0),
        status=SessionStatus.ACTIVE,
        last_sequence_number=0,
        max_capacity=30,
    )

    db.add_all([sess1, sess2, sess3])

    # Demo Staff and Patient Accounts (Configured via backend/.env)
    demo_password_hash = hash_password(demo_password)

    staff1 = User(
        email="staff.citycare@queueless.local",
        password_hash=demo_password_hash,
        full_name="Sister Sunita (Reception Staff)",
        phone="+919441112233",
        role=UserRole.STAFF,
        hospital_id=h1.id,
        is_active=True,
    )
    staff2 = User(
        email="staff.greenlife@queueless.local",
        password_hash=demo_password_hash,
        full_name="Ramesh Kumar (Desk Staff)",
        phone="+919442223344",
        role=UserRole.STAFF,
        hospital_id=h2.id,
        is_active=True,
    )
    demo_patient = User(
        email="patient.demo@queueless.local",
        password_hash=demo_password_hash,
        full_name="Karthik Subramanian",
        phone="+919840011223",
        role=UserRole.PATIENT,
        hospital_id=None,
        is_active=True,
    )

    db.add_all([staff1, staff2, demo_patient])
    db.commit()
    print("[SUCCESS] Fictional demonstration data and demo accounts seeded successfully.")


def run_seed():
    """Main execution function for initializing tables and seeding."""
    print("=" * 60)
    print("QueueLess: Initializing Database Schema & Seed Data")
    print("=" * 60)

    # Pre-flight credential validation: ensures both passwords are provided before any DB action
    admin_password, demo_password = validate_seed_credentials()

    try:
        print("[INFO] Creating tables if not already present...")
        Base.metadata.create_all(bind=engine)
        print("[SUCCESS] Database tables verified.")

        with SessionLocal() as db:
            get_or_create_admin(db, admin_password)
            seed_demo_data(db, demo_password)

            # Verification of tables and counts
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = sorted(inspector.get_table_names())

            hosp_count = db.query(Hospital).count()
            dept_count = db.query(Department).count()
            doc_count = db.query(Doctor).count()
            sess_count = db.query(ConsultationSession).count()
            user_count = db.query(User).count()
            ticket_count = db.query(QueueTicket).count()

            print("\n" + "=" * 60)
            print(f"DATABASE VERIFICATION REPORT (Database: {settings.DB_NAME})")
            print("=" * 60)
            print(f"Tables present ({len(tables)}): {', '.join(tables)}")
            print("-" * 60)
            print(f"  • Hospitals:             {hosp_count}")
            print(f"  • Departments:           {dept_count}")
            print(f"  • Doctors:               {doc_count}")
            print(f"  • Consultation Sessions: {sess_count}")
            print(f"  • Users:                 {user_count}")
            print(f"  • Queue Tickets:         {ticket_count}")
            print("=" * 60)

        print("\n[COMPLETE] Database initialization finished successfully.")
    except Exception as e:
        print(f"\n[ERROR] Database initialization failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_seed()
