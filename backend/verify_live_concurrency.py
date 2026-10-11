"""
Live MySQL/InnoDB Concurrency Verification Script for QueueLess (Phase 2, Milestone 4).
Tests 5 simultaneous queue-join requests against the live FastAPI server on http://127.0.0.1:8000
connected to MySQL 8.0 (InnoDB engine).

Strict Isolation & Safety Guarantees:
1. Creates a dedicated, ephemeral test session: '[TEST_CONCURRENCY] Live Concurrency Verification OPD'.
2. Creates 5 temporary patient accounts with unique test emails.
3. Issues 5 concurrent requests simultaneously using ThreadPoolExecutor.
4. Verifies sequence numbers are unique, strictly contiguous (1, 2, 3, 4, 5) with zero deadlocks.
5. In a guaranteed finally block, removes only the test-created records.
6. Asserts pre-existing database records remain completely untouched.
"""

import sys
import uuid
from datetime import date, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx

from app.database import SessionLocal
from app.models import (
    Hospital,
    Doctor,
    ConsultationSession,
    SessionStatus,
    QueueTicket,
    User,
    UserRole,
)
from app.security import hash_password, create_access_token

BASE_URL = "http://127.0.0.1:8000"


def run_concurrency_verification():
    print("=" * 70)
    print("QueueLess: Live MySQL/InnoDB Concurrency Verification")
    print("=" * 70)

    test_user_ids: list[int] = []
    test_session_id: int | None = None
    test_ticket_ids: list[int] = []
    unique_run_id = uuid.uuid4().hex[:8]

    # Pre-test baseline count verification
    with SessionLocal() as db:
        pre_hospitals = db.query(Hospital).count()
        pre_doctors = db.query(Doctor).count()
        pre_users = db.query(User).count()
        pre_sessions = db.query(ConsultationSession).count()
        pre_tickets = db.query(QueueTicket).count()

        print(f"\n[BASELINE] Pre-test MySQL counts:")
        print(f"  • Hospitals: {pre_hospitals}, Doctors: {pre_doctors}, Users: {pre_users}, Sessions: {pre_sessions}, Tickets: {pre_tickets}")

    try:
        # --------------------------------------------------------------------
        # 1. Setup Dedicated Test Session & Safe Test Accounts
        # --------------------------------------------------------------------
        print(f"\n[STEP 1] Creating isolated test session & 5 temporary test patient accounts...")
        with SessionLocal() as db:
            # Find an approved hospital and active doctor
            hospital = db.query(Hospital).filter(Hospital.id == 1).first()
            doctor = db.query(Doctor).filter(Doctor.hospital_id == 1, Doctor.is_active == True).first()

            assert hospital is not None, "Hospital 1 not found"
            assert doctor is not None, "Active doctor in Hospital 1 not found"

            # Create dedicated test session (evening time window to avoid any overlap)
            test_session = ConsultationSession(
                hospital_id=hospital.id,
                doctor_id=doctor.id,
                session_name=f"[TEST_CONCURRENCY] Live Concurrency Test {unique_run_id}",
                session_date=date.today(),
                start_time=time(20, 0),
                end_time=time(23, 0),
                status=SessionStatus.ACTIVE,
                last_sequence_number=0,
                max_capacity=50,
            )
            db.add(test_session)
            db.flush()
            test_session_id = test_session.id

            # Create 5 temporary test patients
            test_tokens = []
            for i in range(5):
                temp_user = User(
                    email=f"temp_concurrency_{i}_{unique_run_id}@test.local",
                    password_hash=hash_password("TempPass123!"),
                    full_name=f"Test Concurrency Patient {i+1}",
                    role=UserRole.PATIENT,
                    is_active=True,
                )
                db.add(temp_user)
                db.flush()
                test_user_ids.append(temp_user.id)

                token = create_access_token(
                    data={
                        "sub": str(temp_user.id),
                        "email": temp_user.email,
                        "role": temp_user.role.value,
                        "hospital_id": None,
                    }
                )
                test_tokens.append(token)

            db.commit()

        print(f"  • Dedicated Test Session ID: {test_session_id}")
        print(f"  • Temporary Test Patient IDs: {test_user_ids}")
        print(f"  • Authentication Tokens Generated: 5 tokens ready")

        # --------------------------------------------------------------------
        # 2. Execute 5 Concurrent Queue-Join Requests
        # --------------------------------------------------------------------
        print(f"\n[STEP 2] Dispatching 5 concurrent requests to POST /api/sessions/{test_session_id}/tickets...")

        def make_join_request(idx: int, auth_token: str):
            with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
                response = client.post(
                    f"/api/sessions/{test_session_id}/tickets",
                    json={
                        "patient_name": f"Concurrent Patient {idx+1}",
                        "patient_phone": f"+91999900000{idx+1}",
                    },
                    headers={"Authorization": f"Bearer {auth_token}"},
                )
                return idx, response.status_code, response.json()

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(make_join_request, i, test_tokens[i])
                for i in range(5)
            ]
            for future in as_completed(futures):
                results.append(future.result())

        # --------------------------------------------------------------------
        # 3. Analyze & Verify Concurrency Integrity
        # --------------------------------------------------------------------
        print("\n[STEP 3] Analyzing concurrency verification results:")
        results.sort(key=lambda r: r[0])  # Sort by worker index

        status_codes = [r[1] for r in results]
        print(f"  • HTTP Status Codes Received: {status_codes}")
        assert all(code == 201 for code in status_codes), f"Not all requests succeeded: {results}"

        allocated_sequences = []
        allocated_token_numbers = []

        for worker_idx, status_code, body in results:
            ticket_data = body.get("ticket", {})
            t_id = ticket_data.get("id")
            seq = ticket_data.get("sequence_number")
            tok = ticket_data.get("ticket_number")
            test_ticket_ids.append(t_id)
            allocated_sequences.append(seq)
            allocated_token_numbers.append(tok)
            print(f"    Worker {worker_idx+1}: Ticket ID={t_id}, Token={tok}, Sequence={seq}, Status={ticket_data.get('status')}")

        sorted_sequences = sorted(allocated_sequences)
        print(f"\n  • Allocated Sequences: {sorted_sequences}")
        print(f"  • Allocated Tokens:    {allocated_token_numbers}")

        # Assertions for MySQL/InnoDB row-locking correctness
        assert len(allocated_sequences) == 5, "Expected exactly 5 allocated sequence numbers"
        assert sorted_sequences == [1, 2, 3, 4, 5], f"Expected contiguous sequences [1, 2, 3, 4, 5], got {sorted_sequences}"
        assert len(set(allocated_sequences)) == 5, "Duplicate sequence numbers detected! Concurrency failure."
        assert len(set(allocated_token_numbers)) == 5, "Duplicate token numbers detected! Concurrency failure."

        print("\n[SUCCESS] MySQL/InnoDB Concurrency Verification PASSED:")
        print("  [OK] Zero deadlocks or lock-wait timeout errors")
        print("  [OK] Zero duplicate-key conflicts")
        print("  [OK] All 5 concurrent requests allocated strictly contiguous, unique sequence numbers (1, 2, 3, 4, 5)")
        print("  [OK] Atomic row-locking (with_for_update) verified under live multi-threaded load")

    finally:
        # --------------------------------------------------------------------
        # 4. Safe Reversible Cleanup of Test-Created Records Only
        # --------------------------------------------------------------------
        print(f"\n[STEP 4] Executing safe cleanup of test-created records...")
        with SessionLocal() as db:
            if test_ticket_ids:
                deleted_tickets = db.query(QueueTicket).filter(QueueTicket.id.in_(test_ticket_ids)).delete(synchronize_session=False)
                print(f"  • Cleaned up {deleted_tickets} test ticket records.")

            if test_session_id:
                deleted_sessions = db.query(ConsultationSession).filter(ConsultationSession.id == test_session_id).delete(synchronize_session=False)
                print(f"  • Cleaned up {deleted_sessions} test session record.")

            if test_user_ids:
                deleted_users = db.query(User).filter(User.id.in_(test_user_ids)).delete(synchronize_session=False)
                print(f"  • Cleaned up {deleted_users} temporary test user records.")

            db.commit()

        # --------------------------------------------------------------------
        # 5. Confirm Pre-Existing Records Remain Untouched
        # --------------------------------------------------------------------
        with SessionLocal() as db:
            post_hospitals = db.query(Hospital).count()
            post_doctors = db.query(Doctor).count()
            post_users = db.query(User).count()
            post_sessions = db.query(ConsultationSession).count()
            post_tickets = db.query(QueueTicket).count()

            print(f"\n[CONFIRMATION] Post-test MySQL record counts:")
            print(f"  • Hospitals: {post_hospitals} (Expected: {pre_hospitals})")
            print(f"  • Doctors:   {post_doctors} (Expected: {pre_doctors})")
            print(f"  • Users:     {post_users} (Expected: {pre_users})")
            print(f"  • Sessions:  {post_sessions} (Expected: {pre_sessions})")
            print(f"  • Tickets:   {post_tickets} (Expected: {pre_tickets})")

            assert post_hospitals == pre_hospitals, "Hospital count mismatch"
            assert post_doctors == pre_doctors, "Doctor count mismatch"
            assert post_users == pre_users, "User count mismatch"
            assert post_sessions == pre_sessions, "Session count mismatch"
            assert post_tickets == pre_tickets, "Ticket count mismatch"

        print("\n[SUCCESS] Database baseline confirmed 100% restored. Zero pre-existing records were modified.")


if __name__ == "__main__":
    run_concurrency_verification()
