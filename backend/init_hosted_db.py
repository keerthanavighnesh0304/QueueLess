"""
QueueLess Hosted Database Safe Initialization & Idempotent Seed Tool

Strictly reserved for hosted MySQL databases (e.g. Aiven MySQL on Render).
Refuses to execute against localhost / 127.0.0.1 loopback targets.
Requires explicit '--confirm-hosted' confirmation flag.

Does not drop tables, truncate records, or overwrite existing passwords.
Creates missing tables using SQLAlchemy model metadata and seeds fictional
demonstration data with future-dated consultation sessions.
"""

import argparse
import os
import sys
import urllib.parse
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings
from app.database import Base
from app.models import (
    ConsultationSession,
    Department,
    Doctor,
    Hospital,
    HospitalStatus,
    QueueTicket,
    SessionStatus,
    User,
    UserRole,
)
from app.security import hash_password


LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", ""})


def validate_hosted_target(host: Optional[str]) -> None:
    """
    Guards against accidental execution on local development environments.
    Raises ValueError immediately if the target host is loopback or localhost.
    """
    clean_host = (host or "").strip().lower()
    if clean_host in LOOPBACK_HOSTS or clean_host.endswith(".local") or clean_host == "none":
        raise ValueError(
            f"[REFUSED] Target database host '{host}' is a localhost/loopback address. "
            "This script is strictly reserved for hosted databases (e.g., Aiven MySQL). "
            "Local development databases must NOT be initialized using this script."
        )


def validate_seed_credentials() -> tuple[str, str]:
    """
    Ensures admin and demo account credentials are non-empty before touching the database.
    Reads from environment variables and does not log secret values.
    """
    admin_password = (os.getenv("ADMIN_INITIAL_PASSWORD") or "").strip()
    demo_password = (os.getenv("DEMO_ACCOUNTS_PASSWORD") or "").strip()

    missing = []
    if not admin_password:
        missing.append("ADMIN_INITIAL_PASSWORD")
    if not demo_password:
        missing.append("DEMO_ACCOUNTS_PASSWORD")

    if missing:
        raise ValueError(
            f"[REFUSED] Required credential environment variable(s) missing or empty: {', '.join(missing)}. "
            "Configure them in your hosted environment before running initialization."
        )

    return admin_password, demo_password


def resolve_database_config(
    database_url: Optional[str] = None,
) -> tuple[str, dict[str, Any], str]:
    """
    Resolves the database URL and DBAPI connect_args.
    Supports Render environment configuration:
    - Prioritizes explicit DATABASE_URL if configured.
    - Otherwise builds connection from discrete DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_SSL_MODE.
    Reuses Settings TLS/SSL connection handling.
    Returns (normalized_url, connect_args, host_for_validation).
    """
    explicit_url = database_url or os.getenv("HOSTED_DATABASE_URL") or os.getenv("DATABASE_URL")

    # Instantiate Settings reading current process environment without local .env pollution
    effective_settings = Settings(
        _env_file=None,
        DATABASE_URL=explicit_url if (explicit_url and explicit_url.strip()) else None,
        DB_HOST=os.getenv("DB_HOST", "127.0.0.1"),
        DB_PORT=int(os.getenv("DB_PORT", "3306")),
        DB_USER=os.getenv("DB_USER", "root"),
        DB_PASSWORD=os.getenv("DB_PASSWORD", ""),
        DB_NAME=os.getenv("DB_NAME", "defaultdb"),
        DB_SSL_CA=os.getenv("DB_SSL_CA"),
        DB_SSL_CHECK_HOSTNAME=os.getenv("DB_SSL_CHECK_HOSTNAME", "true").lower() not in {"false", "0", "no"},
        DB_SSL_MODE=os.getenv("DB_SSL_MODE"),
    )

    resolved_url = effective_settings.get_database_url()
    connect_args = effective_settings.get_database_connect_args()

    # Determine host for safety validation
    if effective_settings.DATABASE_URL:
        parsed = urllib.parse.urlsplit(resolved_url)
        host = parsed.hostname or ""
    else:
        host = effective_settings.DB_HOST

    return resolved_url, connect_args, host


def get_or_create_admin(db: Session, admin_password: str, admin_email: str) -> tuple[User, bool]:
    """
    Safely retrieves or provisions the initial administrator account.
    Never overwrites an existing admin password.
    """
    existing_admin = db.query(User).filter(User.email == admin_email).first()
    if existing_admin:
        return existing_admin, False

    admin = User(
        email=admin_email,
        password_hash=hash_password(admin_password),
        full_name=os.getenv("ADMIN_FULL_NAME", "Platform Administrator"),
        phone="+919876543210",
        role=UserRole.ADMIN,
        hospital_id=None,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin, True


def seed_demo_entities(
    db: Session,
    demo_password: str,
    base_date: Optional[date] = None,
) -> dict[str, int]:
    """
    Idempotently seeds fictional demonstration hospitals, departments, doctors,
    users, and future-dated consultation sessions.
    Inspects existing records prior to insert. Never modifies or deletes records.
    Returns counts of newly created entities.
    """
    if base_date is None:
        base_date = date.today()

    demo_password_hash = hash_password(demo_password)
    stats = {
        "hospitals_created": 0,
        "departments_created": 0,
        "doctors_created": 0,
        "users_created": 0,
        "sessions_created": 0,
    }

    # 1. Hospitals
    hospitals_spec = [
        {
            "name": "[Demo] City Care Hospital",
            "registration_number": "DEMO-HOSP-001",
            "address": "124 Cross Cut Road, Gandhipuram",
            "city": "Coimbatore",
            "latitude": 11.016844,
            "longitude": 76.955832,
            "status": HospitalStatus.APPROVED,
            "is_accepting_bookings": True,
            "avg_consultation_time_mins": 15,
        },
        {
            "name": "[Demo] Green Life Clinic",
            "registration_number": "DEMO-HOSP-002",
            "address": "45 DB Road, RS Puram",
            "city": "Coimbatore",
            "latitude": 11.008920,
            "longitude": 76.942710,
            "status": HospitalStatus.APPROVED,
            "is_accepting_bookings": True,
            "avg_consultation_time_mins": 10,
        },
        {
            "name": "[Demo] Sunrise Medical Center",
            "registration_number": "DEMO-HOSP-003",
            "address": "88 Avinashi Road, Peelamedu",
            "city": "Coimbatore",
            "latitude": 11.028010,
            "longitude": 77.005020,
            "status": HospitalStatus.PENDING_APPROVAL,
            "is_accepting_bookings": False,
            "avg_consultation_time_mins": 20,
        },
    ]

    hosp_map: dict[str, Hospital] = {}
    for spec in hospitals_spec:
        reg_no = spec["registration_number"]
        h = db.query(Hospital).filter(Hospital.registration_number == reg_no).first()
        if not h:
            h = Hospital(**spec)
            db.add(h)
            db.flush()
            stats["hospitals_created"] += 1
        hosp_map[reg_no] = h

    # 2. Departments
    departments_spec = [
        {"hospital": hosp_map["DEMO-HOSP-001"], "name": "General Medicine", "description": "Primary care & diagnosis"},
        {"hospital": hosp_map["DEMO-HOSP-001"], "name": "Pediatrics", "description": "Child health & immunization"},
        {"hospital": hosp_map["DEMO-HOSP-002"], "name": "Cardiology", "description": "Heart & vascular consultations"},
    ]

    dept_map: dict[tuple[int, str], Department] = {}
    for spec in departments_spec:
        h = spec["hospital"]
        name = spec["name"]
        d = db.query(Department).filter(
            Department.hospital_id == h.id,
            Department.name == name,
        ).first()
        if not d:
            d = Department(hospital_id=h.id, name=name, description=spec["description"])
            db.add(d)
            db.flush()
            stats["departments_created"] += 1
        dept_map[(h.id, name)] = d

    # 3. Doctors
    doctors_spec = [
        {
            "hospital": hosp_map["DEMO-HOSP-001"],
            "dept": dept_map[(hosp_map["DEMO-HOSP-001"].id, "General Medicine")],
            "full_name": "Dr. A. Sharma, MBBS, MD",
            "qualification": "MD - General Medicine",
            "specialization": "Internal Medicine",
            "ticket_prefix": "GEN",
            "avg_consultation_time_mins": 15,
        },
        {
            "hospital": hosp_map["DEMO-HOSP-001"],
            "dept": dept_map[(hosp_map["DEMO-HOSP-001"].id, "Pediatrics")],
            "full_name": "Dr. R. Priya, DCH",
            "qualification": "MBBS, DCH",
            "specialization": "Pediatrics",
            "ticket_prefix": "PED",
            "avg_consultation_time_mins": 12,
        },
        {
            "hospital": hosp_map["DEMO-HOSP-002"],
            "dept": dept_map[(hosp_map["DEMO-HOSP-002"].id, "Cardiology")],
            "full_name": "Dr. K. Anand, DM",
            "qualification": "MD, DM (Cardiology)",
            "specialization": "Cardiology",
            "ticket_prefix": "CARD",
            "avg_consultation_time_mins": 20,
        },
    ]

    doc_map: dict[tuple[int, str], Doctor] = {}
    for spec in doctors_spec:
        h = spec["hospital"]
        d = spec["dept"]
        full_name = spec["full_name"]
        doc = db.query(Doctor).filter(
            Doctor.hospital_id == h.id,
            Doctor.full_name == full_name,
        ).first()
        if not doc:
            doc = Doctor(
                hospital_id=h.id,
                department_id=d.id,
                full_name=full_name,
                qualification=spec["qualification"],
                specialization=spec["specialization"],
                ticket_prefix=spec["ticket_prefix"],
                avg_consultation_time_mins=spec["avg_consultation_time_mins"],
                is_active=True,
            )
            db.add(doc)
            db.flush()
            stats["doctors_created"] += 1
        doc_map[(h.id, full_name)] = doc

    # 4. Users (Staff & Patient)
    users_spec = [
        {
            "email": "staff.citycare@queueless.local",
            "full_name": "Sister Sunita (Reception Staff)",
            "phone": "+919441112233",
            "role": UserRole.STAFF,
            "hospital_id": hosp_map["DEMO-HOSP-001"].id,
        },
        {
            "email": "staff.greenlife@queueless.local",
            "full_name": "Ramesh Kumar (Desk Staff)",
            "phone": "+919442223344",
            "role": UserRole.STAFF,
            "hospital_id": hosp_map["DEMO-HOSP-002"].id,
        },
        {
            "email": "patient.demo@queueless.local",
            "full_name": "Karthik Subramanian",
            "phone": "+919840011223",
            "role": UserRole.PATIENT,
            "hospital_id": None,
        },
    ]

    for spec in users_spec:
        u = db.query(User).filter(User.email == spec["email"]).first()
        if not u:
            u = User(
                email=spec["email"],
                password_hash=demo_password_hash,
                full_name=spec["full_name"],
                phone=spec["phone"],
                role=spec["role"],
                hospital_id=spec["hospital_id"],
                is_active=True,
            )
            db.add(u)
            db.flush()
            stats["users_created"] += 1

    # 5. Future-dated Consultation Sessions (Today + next 3 calendar days = 4 days)
    doc_sharma = doc_map[(hosp_map["DEMO-HOSP-001"].id, "Dr. A. Sharma, MBBS, MD")]
    doc_priya = doc_map[(hosp_map["DEMO-HOSP-001"].id, "Dr. R. Priya, DCH")]
    doc_anand = doc_map[(hosp_map["DEMO-HOSP-002"].id, "Dr. K. Anand, DM")]

    for day_offset in range(4):
        target_date = base_date + timedelta(days=day_offset)
        # Day 0 (today) and Day 1 (tomorrow) are ACTIVE for immediate queue interactions;
        # Days 2 and 3 are SCHEDULED
        sess_status = SessionStatus.ACTIVE if day_offset <= 1 else SessionStatus.SCHEDULED

        sessions_spec = [
            {
                "hospital_id": hosp_map["DEMO-HOSP-001"].id,
                "doctor_id": doc_sharma.id,
                "session_name": "Morning General OPD",
                "session_date": target_date,
                "start_time": time(9, 0),
                "end_time": time(13, 0),
                "status": sess_status,
                "max_capacity": 50,
            },
            {
                "hospital_id": hosp_map["DEMO-HOSP-001"].id,
                "doctor_id": doc_priya.id,
                "session_name": "Morning Pediatric OPD",
                "session_date": target_date,
                "start_time": time(9, 30),
                "end_time": time(13, 30),
                "status": sess_status,
                "max_capacity": 40,
            },
            {
                "hospital_id": hosp_map["DEMO-HOSP-002"].id,
                "doctor_id": doc_anand.id,
                "session_name": "Cardiology Specialist Clinic",
                "session_date": target_date,
                "start_time": time(10, 0),
                "end_time": time(14, 0),
                "status": sess_status,
                "max_capacity": 30,
            },
        ]

        for s_spec in sessions_spec:
            existing_sess = db.query(ConsultationSession).filter(
                ConsultationSession.hospital_id == s_spec["hospital_id"],
                ConsultationSession.doctor_id == s_spec["doctor_id"],
                ConsultationSession.session_date == s_spec["session_date"],
                ConsultationSession.session_name == s_spec["session_name"],
            ).first()

            if not existing_sess:
                new_sess = ConsultationSession(
                    hospital_id=s_spec["hospital_id"],
                    doctor_id=s_spec["doctor_id"],
                    session_name=s_spec["session_name"],
                    session_date=s_spec["session_date"],
                    start_time=s_spec["start_time"],
                    end_time=s_spec["end_time"],
                    status=s_spec["status"],
                    last_sequence_number=0,
                    max_capacity=s_spec["max_capacity"],
                )
                db.add(new_sess)
                db.flush()
                stats["sessions_created"] += 1

    db.commit()
    return stats


def initialize_hosted_database(
    database_url: Optional[str] = None,
    confirm_hosted: bool = False,
    base_date: Optional[date] = None,
) -> dict[str, Any]:
    """
    Main entry point for initializing the hosted database schema and seed data.
    Validates safety rules, establishes isolated engine, creates missing tables,
    and idempotently populates demonstration records.
    """
    if not confirm_hosted:
        raise ValueError(
            "[REFUSED] Missing required confirmation flag '--confirm-hosted'. "
            "You must supply '--confirm-hosted' to initialize the hosted database."
        )

    # 1. Resolve configuration and enforce localhost blockade
    target_url, connect_args, target_host = resolve_database_config(database_url)
    validate_hosted_target(target_host)

    # 2. Validate non-empty credentials
    admin_password, demo_password = validate_seed_credentials()
    admin_email = (os.getenv("ADMIN_EMAIL") or "admin@queueless.local").strip()

    print("=" * 60)
    print("QueueLess: Safe Hosted Database Initialization")
    print(f"[TARGET HOST]: {target_host}")
    print("=" * 60)

    # 3. Create isolated engine (never uses global app.database.engine)
    isolated_engine = create_engine(
        target_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )

    try:
        # Inspect existing schema prior to DDL
        inspector = inspect(isolated_engine)
        initial_tables = set(inspector.get_table_names())

        print(f"[INFO] Existing tables ({len(initial_tables)}): {', '.join(sorted(initial_tables)) or 'None'}")
        print("[INFO] Creating missing tables using SQLAlchemy model metadata...")
        Base.metadata.create_all(bind=isolated_engine)

        inspector_after = inspect(isolated_engine)
        final_tables = set(inspector_after.get_table_names())
        created_tables = final_tables - initial_tables

        if created_tables:
            print(f"[SUCCESS] Created tables ({len(created_tables)}): {', '.join(sorted(created_tables))}")
        else:
            print("[INFO] All tables are already present in the database.")

        # 4. Idempotently seed entities using isolated session
        IsolatedSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=isolated_engine)
        with IsolatedSessionLocal() as db:
            admin_user, admin_created = get_or_create_admin(db, admin_password, admin_email)
            if admin_created:
                print(f"[SUCCESS] Admin account provisioned: {admin_email}")
            else:
                print(f"[INFO] Admin account '{admin_email}' already exists. Preserving record.")

            stats = seed_demo_entities(db, demo_password, base_date=base_date)

            # Verification of counts
            hosp_count = db.query(Hospital).count()
            dept_count = db.query(Department).count()
            doc_count = db.query(Doctor).count()
            sess_count = db.query(ConsultationSession).count()
            user_count = db.query(User).count()
            ticket_count = db.query(QueueTicket).count()

        print("\n" + "=" * 60)
        print("DATABASE INITIALIZATION & VERIFICATION SUMMARY")
        print("=" * 60)
        print(f"  • Total Tables in Schema:   {len(final_tables)}")
        print(f"  • Hospitals:                {hosp_count} (New: {stats['hospitals_created']})")
        print(f"  • Departments:              {dept_count} (New: {stats['departments_created']})")
        print(f"  • Doctors:                  {doc_count} (New: {stats['doctors_created']})")
        print(f"  • Consultation Sessions:    {sess_count} (New: {stats['sessions_created']})")
        print(f"  • Users:                    {user_count} (New: {stats['users_created'] + (1 if admin_created else 0)})")
        print(f"  • Queue Tickets:            {ticket_count}")
        print("=" * 60)
        print("[COMPLETE] Hosted database initialization completed successfully.")

        return {
            "tables": sorted(final_tables),
            "hosp_count": hosp_count,
            "sess_count": sess_count,
            "user_count": user_count,
            "stats": stats,
        }
    finally:
        isolated_engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Safe, idempotent initialization for hosted Aiven MySQL database."
    )
    parser.add_argument(
        "--confirm-hosted",
        action="store_true",
        help="Mandatory confirmation flag required to run against a hosted database.",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Optional explicit connection URL (e.g. mysql+pymysql://user:pass@host:port/db).",
    )

    args = parser.parse_args()

    try:
        initialize_hosted_database(
            database_url=args.database_url,
            confirm_hosted=args.confirm_hosted,
        )
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
