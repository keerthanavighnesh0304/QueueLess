from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.database import get_db
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
)
from app.schemas import (
    HospitalRegisterRequest,
    HospitalOut,
    HospitalDetailOut,
    DepartmentOut,
    DoctorOut,
    ConsultationSessionOut,
    ConsultationSessionCreateRequest,
    ConsultationSessionStatusUpdateRequest,
    ConsultationSessionActionResponse,
    WalkInTicketRequest,
    QueueTicketStaffOut,
    LiveQueueSummaryOut,
    TicketActionResponse,
    CallNextResponse,
)
from app.dependencies import require_hospital_staff

router = APIRouter()


# ============================================================================
# Relationship & Access Validation Helpers
# ============================================================================

def get_approved_hospital_or_404(hospital_id: int, db: Session) -> Hospital:
    """
    Retrieves an approved hospital eligible for bookings.
    Returns 404 if the hospital does not exist, is pending, rejected, or suspended,
    preventing unapproved facilities from being discovered or probed.
    """
    hospital = db.query(Hospital).filter(
        Hospital.id == hospital_id,
        Hospital.status == HospitalStatus.APPROVED,
        Hospital.is_accepting_bookings == True,
    ).first()

    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found or not currently accepting bookings",
        )
    return hospital


def get_hospital_department_or_404(hospital_id: int, department_id: int, db: Session) -> Department:
    """
    Validates that a department exists and strictly belongs to the specified hospital.
    """
    department = db.query(Department).filter(
        Department.id == department_id,
        Department.hospital_id == hospital_id,
    ).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found in this hospital",
        )
    return department


def get_hospital_doctor_or_404(
    hospital_id: int,
    doctor_id: int,
    db: Session,
    active_only: bool = True,
) -> Doctor:
    """
    Validates that a doctor exists and strictly belongs to the specified hospital.
    """
    query = db.query(Doctor).filter(
        Doctor.id == doctor_id,
        Doctor.hospital_id == hospital_id,
    )
    if active_only:
        query = query.filter(Doctor.is_active == True)

    doctor = query.first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found in this hospital",
        )
    return doctor


def get_hospital_session_or_404(
    hospital_id: int,
    session_id: int,
    db: Session,
) -> ConsultationSession:
    """
    Validates that a consultation session exists and strictly belongs to the specified hospital.
    """
    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id,
        ConsultationSession.hospital_id == hospital_id,
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation session not found in this hospital",
        )
    return session


# ============================================================================
# Hospital Onboarding & Public Discovery Endpoints
# ============================================================================

@router.post(
    "/register",
    response_model=HospitalOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new hospital for administrative onboarding",
    responses={
        201: {"description": "Hospital application submitted successfully in pending status"},
        409: {"description": "Hospital with this registration number already exists"},
        422: {"description": "Validation error in coordinates or registration fields"},
    },
)
def register_hospital(
    payload: HospitalRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Submits a new healthcare facility onboarding application.
    Enforces that:
    1. Registration numbers are normalized (trimmed, uppercase).
    2. Duplicates return HTTP 409 Conflict.
    3. Status is strictly forced to PENDING_APPROVAL with bookings disabled.
    4. Client cannot assign roles or administrative privileges.
    """
    normalized_reg_no = payload.registration_number.strip().upper()

    existing = db.query(Hospital).filter(
        Hospital.registration_number == normalized_reg_no
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A hospital with registration number '{normalized_reg_no}' is already registered.",
        )

    hospital = Hospital(
        name=payload.name.strip(),
        registration_number=normalized_reg_no,
        address=payload.address.strip(),
        city=payload.city.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        status=HospitalStatus.PENDING_APPROVAL,
        is_accepting_bookings=False,
        avg_consultation_time_mins=payload.avg_consultation_time_mins,
    )

    try:
        db.add(hospital)
        db.commit()
        db.refresh(hospital)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A hospital with registration number '{normalized_reg_no}' is already registered.",
        )

    return hospital


@router.get(
    "",
    response_model=list[HospitalOut],
    summary="List approved hospitals eligible to accept bookings",
    responses={
        200: {"description": "List of approved hospitals"},
    },
)
@router.get(
    "/",
    response_model=list[HospitalOut],
    include_in_schema=False,
)
def list_hospitals(
    city: Optional[str] = Query(None, description="Filter by city name"),
    search: Optional[str] = Query(None, description="Search by hospital name"),
    db: Session = Depends(get_db),
):
    """
    Public listing of approved hospitals currently eligible to accept bookings.
    Pending, rejected, and suspended hospitals are strictly excluded.
    """
    query = db.query(Hospital).filter(
        Hospital.status == HospitalStatus.APPROVED,
        Hospital.is_accepting_bookings == True,
    )

    if city:
        query = query.filter(func.lower(Hospital.city) == city.strip().lower())

    if search:
        query = query.filter(Hospital.name.ilike(f"%{search.strip()}%"))

    return query.order_by(Hospital.name.asc()).all()


@router.get(
    "/{hospital_id}",
    response_model=HospitalDetailOut,
    summary="Retrieve details of an approved hospital",
    responses={
        200: {"description": "Hospital details including clinical departments"},
        404: {"description": "Hospital not found or not currently accepting bookings"},
    },
)
def get_hospital_details(
    hospital_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieves full details of an approved hospital, including its active clinical departments.
    Returns 404 for non-existent, pending, rejected, or suspended hospitals.
    """
    return get_approved_hospital_or_404(hospital_id, db)


# ============================================================================
# Department & Doctor Catalog Endpoints
# ============================================================================

@router.get(
    "/{hospital_id}/departments",
    response_model=list[DepartmentOut],
    summary="List departments of an approved hospital",
    responses={
        200: {"description": "List of departments belonging to the hospital"},
        404: {"description": "Hospital not found or not accepting bookings"},
    },
)
def list_departments(
    hospital_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns all departments belonging to the specified approved hospital.
    """
    get_approved_hospital_or_404(hospital_id, db)
    return db.query(Department).filter(
        Department.hospital_id == hospital_id
    ).order_by(Department.name.asc()).all()


@router.get(
    "/{hospital_id}/doctors",
    response_model=list[DoctorOut],
    summary="List active doctors for an approved hospital",
    responses={
        200: {"description": "List of active doctors in the hospital"},
        404: {"description": "Hospital or department not found"},
    },
)
def list_doctors(
    hospital_id: int,
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    db: Session = Depends(get_db),
):
    """
    Returns active doctors practicing at the specified approved hospital.
    Validates department ownership if department_id is supplied.
    """
    get_approved_hospital_or_404(hospital_id, db)

    query = db.query(Doctor).filter(
        Doctor.hospital_id == hospital_id,
        Doctor.is_active == True,
    )

    if department_id is not None:
        get_hospital_department_or_404(hospital_id, department_id, db)
        query = query.filter(Doctor.department_id == department_id)

    return query.order_by(Doctor.full_name.asc()).all()


@router.get(
    "/{hospital_id}/doctors/{doctor_id}",
    response_model=DoctorOut,
    summary="Retrieve details of a doctor in an approved hospital",
    responses={
        200: {"description": "Doctor details"},
        404: {"description": "Hospital or doctor not found in this hospital"},
    },
)
def get_doctor_details(
    hospital_id: int,
    doctor_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns doctor profile. Enforces that the doctor belongs to this hospital and is active.
    """
    get_approved_hospital_or_404(hospital_id, db)
    return get_hospital_doctor_or_404(hospital_id, doctor_id, db, active_only=True)


# ============================================================================
# Consultation Sessions Endpoints
# ============================================================================

@router.get(
    "/{hospital_id}/doctors/{doctor_id}/sessions",
    response_model=list[ConsultationSessionOut],
    summary="List consultation sessions for a doctor in an approved hospital",
    responses={
        200: {"description": "List of consultation sessions"},
        404: {"description": "Hospital or doctor not found in this hospital"},
    },
)
def list_doctor_sessions(
    hospital_id: int,
    doctor_id: int,
    session_date: Optional[date] = Query(None, description="Filter by session date (YYYY-MM-DD)"),
    status: Optional[SessionStatus] = Query(None, description="Filter by session status"),
    db: Session = Depends(get_db),
):
    """
    Lists consultation sessions for a specific doctor.
    Defaults to today and upcoming dates unless a specific session_date is specified.
    """
    get_approved_hospital_or_404(hospital_id, db)
    get_hospital_doctor_or_404(hospital_id, doctor_id, db, active_only=False)

    query = db.query(ConsultationSession).filter(
        ConsultationSession.hospital_id == hospital_id,
        ConsultationSession.doctor_id == doctor_id,
    )

    if session_date is not None:
        query = query.filter(ConsultationSession.session_date == session_date)
    else:
        query = query.filter(ConsultationSession.session_date >= date.today())

    if status is not None:
        query = query.filter(ConsultationSession.status == status)

    return query.order_by(
        ConsultationSession.session_date.asc(),
        ConsultationSession.start_time.asc(),
    ).all()


@router.get(
    "/{hospital_id}/sessions",
    response_model=list[ConsultationSessionOut],
    summary="List consultation sessions for an approved hospital",
    responses={
        200: {"description": "List of consultation sessions in the hospital"},
        404: {"description": "Hospital or doctor not found in this hospital"},
    },
)
def list_hospital_sessions(
    hospital_id: int,
    doctor_id: Optional[int] = Query(None, description="Filter by doctor ID"),
    session_date: Optional[date] = Query(None, description="Filter by session date (YYYY-MM-DD)"),
    status: Optional[SessionStatus] = Query(None, description="Filter by session status"),
    db: Session = Depends(get_db),
):
    """
    Lists consultation sessions across doctors for an approved hospital.
    Defaults to today and upcoming dates unless a specific session_date is specified.
    """
    get_approved_hospital_or_404(hospital_id, db)

    query = db.query(ConsultationSession).filter(
        ConsultationSession.hospital_id == hospital_id,
    )

    if doctor_id is not None:
        get_hospital_doctor_or_404(hospital_id, doctor_id, db, active_only=False)
        query = query.filter(ConsultationSession.doctor_id == doctor_id)

    if session_date is not None:
        query = query.filter(ConsultationSession.session_date == session_date)
    else:
        query = query.filter(ConsultationSession.session_date >= date.today())

    if status is not None:
        query = query.filter(ConsultationSession.status == status)

    return query.order_by(
        ConsultationSession.session_date.asc(),
        ConsultationSession.start_time.asc(),
    ).all()


@router.get(
    "/{hospital_id}/sessions/{session_id}",
    response_model=ConsultationSessionOut,
    summary="Retrieve details of a consultation session in an approved hospital",
    responses={
        200: {"description": "Consultation session details"},
        404: {"description": "Hospital or consultation session not found in this hospital"},
    },
)
def get_session_details(
    hospital_id: int,
    session_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns details of a consultation session.
    Verifies that the session belongs to this hospital.
    """
    get_approved_hospital_or_404(hospital_id, db)
    return get_hospital_session_or_404(hospital_id, session_id, db)


# ============================================================================
# Staff-Only Session Management Endpoints (Hospital-Isolated)
# ============================================================================

@router.post(
    "/{hospital_id}/sessions",
    response_model=ConsultationSessionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a consultation session for a doctor in this hospital (Staff/Admin only)",
    responses={
        201: {"description": "Consultation session created successfully"},
        400: {"description": "Validation error in date, time, or doctor status"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - staff isolation violation or insufficient privileges"},
        404: {"description": "Hospital or doctor not found in this hospital"},
        409: {"description": "Conflict - overlapping or duplicate session for this doctor"},
    },
)
def create_consultation_session(
    hospital_id: int,
    payload: ConsultationSessionCreateRequest,
    current_user: User = Depends(require_hospital_staff),
    db: Session = Depends(get_db),
):
    """
    Creates an authoritative OPD consultation session for a doctor.
    Enforces:
    1. Hospital-level isolation: Staff must be assigned to this hospital.
    2. Hospital must exist and be in APPROVED status.
    3. Doctor must exist, be active, and belong to this hospital.
    4. Session date cannot be in the past.
    5. Session start_time must precede end_time.
    6. Doctor cannot have overlapping/conflicting sessions on the same date.
    """
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )
    if hospital.status != HospitalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot schedule sessions for hospital with status '{hospital.status.value}'",
        )

    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor or doctor.hospital_id != hospital_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found in this hospital",
        )
    if not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot schedule sessions for an inactive doctor",
        )

    if payload.session_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session date cannot be in the past",
        )

    if payload.start_time is not None and payload.end_time is not None:
        if payload.start_time >= payload.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session start_time must be strictly earlier than end_time",
            )

    # Check for duplicate session names or overlapping time windows on the same date
    existing_sessions = db.query(ConsultationSession).filter(
        ConsultationSession.doctor_id == payload.doctor_id,
        ConsultationSession.session_date == payload.session_date,
        ConsultationSession.status.in_([SessionStatus.SCHEDULED, SessionStatus.ACTIVE, SessionStatus.PAUSED]),
    ).all()

    clean_session_name = payload.session_name.strip()
    for existing in existing_sessions:
        if existing.session_name.strip().lower() == clean_session_name.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A session named '{clean_session_name}' already exists for this doctor on {payload.session_date}",
            )

        if (
            payload.start_time is not None
            and payload.end_time is not None
            and existing.start_time is not None
            and existing.end_time is not None
        ):
            if payload.start_time < existing.end_time and payload.end_time > existing.start_time:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Session time ({payload.start_time} - {payload.end_time}) overlaps with "
                        f"existing session '{existing.session_name}' ({existing.start_time} - {existing.end_time})"
                    ),
                )
        elif (
            payload.start_time is None
            and payload.end_time is None
            and existing.start_time is None
            and existing.end_time is None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An all-day session is already scheduled for this doctor on this date",
            )

    new_session = ConsultationSession(
        hospital_id=hospital_id,
        doctor_id=payload.doctor_id,
        session_name=clean_session_name,
        session_date=payload.session_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=SessionStatus.SCHEDULED,
        last_sequence_number=0,
        max_capacity=payload.max_capacity,
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return new_session


@router.patch(
    "/{hospital_id}/sessions/{session_id}/status",
    response_model=ConsultationSessionActionResponse,
    summary="Update operational status of a consultation session (Staff/Admin only)",
    responses={
        200: {"description": "Session status updated successfully"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - staff isolation violation or insufficient privileges"},
        404: {"description": "Hospital or session not found in this hospital"},
        409: {"description": "Conflict - invalid status transition or attempted reopening of completed session"},
    },
)
def update_session_status(
    hospital_id: int,
    session_id: int,
    payload: ConsultationSessionStatusUpdateRequest,
    current_user: User = Depends(require_hospital_staff),
    db: Session = Depends(get_db),
):
    """
    Updates the operational lifecycle status of an OPD consultation session.
    Enforces valid state machine transitions:
    - SCHEDULED -> ACTIVE, PAUSED, COMPLETED
    - ACTIVE -> PAUSED, COMPLETED
    - PAUSED -> ACTIVE, COMPLETED
    - COMPLETED -> Cannot be transitioned or reopened (HTTP 409 Conflict).
    """
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )

    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id,
        ConsultationSession.hospital_id == hospital_id,
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation session not found in this hospital",
        )

    current_status = session.status
    new_status = payload.status

    if current_status == new_status:
        return ConsultationSessionActionResponse(
            message=f"Session is already in {new_status.value} status",
            session=ConsultationSessionOut.model_validate(session),
        )

    if current_status == SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed consultation sessions cannot be reopened",
        )

    valid_transitions = {
        SessionStatus.SCHEDULED: {SessionStatus.ACTIVE, SessionStatus.PAUSED, SessionStatus.COMPLETED},
        SessionStatus.ACTIVE: {SessionStatus.PAUSED, SessionStatus.COMPLETED},
        SessionStatus.PAUSED: {SessionStatus.ACTIVE, SessionStatus.COMPLETED},
    }

    allowed = valid_transitions.get(current_status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid session status transition from {current_status.value} to {new_status.value}",
        )

    session.status = new_status
    db.commit()
    db.refresh(session)

    return ConsultationSessionActionResponse(
        message=f"Session status updated from {current_status.value} to {new_status.value}",
        session=ConsultationSessionOut.model_validate(session),
    )


# ============================================================================
# Staff-Only Live Queue & Token Operations (Milestone 4)
# ============================================================================

@router.get(
    "/{hospital_id}/sessions/{session_id}/queue",
    response_model=LiveQueueSummaryOut,
    summary="Retrieve live OPD queue dashboard for hospital staff",
    responses={
        200: {"description": "Live queue summary for the session"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - staff isolation violation"},
        404: {"description": "Hospital or session not found in this hospital"},
    },
)
def get_live_queue(
    hospital_id: int,
    session_id: int,
    current_user: User = Depends(require_hospital_staff),
    db: Session = Depends(get_db),
):
    """
    Returns the operational live queue dashboard for a consultation session:
    - Currently called patient
    - Currently serving patient
    - Full list of waiting patients ordered by sequence
    - Real-time capacity utilization
    """
    session = get_hospital_session_or_404(hospital_id, session_id, db)
    doctor = db.query(Doctor).filter(Doctor.id == session.doctor_id).first()

    calling_ticket = db.query(QueueTicket).filter(
        QueueTicket.session_id == session_id,
        QueueTicket.status == TicketStatus.CALLING,
    ).first()

    serving_ticket = db.query(QueueTicket).filter(
        QueueTicket.session_id == session_id,
        QueueTicket.status == TicketStatus.IN_CONSULTATION,
    ).first()

    waiting_tickets = db.query(QueueTicket).filter(
        QueueTicket.session_id == session_id,
        QueueTicket.status == TicketStatus.WAITING,
    ).order_by(QueueTicket.sequence_number.asc()).all()

    consumed_count = db.query(QueueTicket).filter(
        QueueTicket.session_id == session_id,
        QueueTicket.status.in_([
            TicketStatus.WAITING,
            TicketStatus.CALLING,
            TicketStatus.IN_CONSULTATION,
            TicketStatus.COMPLETED,
        ]),
    ).count()

    return LiveQueueSummaryOut(
        session_id=session.id,
        session_name=session.session_name,
        session_status=session.status,
        doctor_id=doctor.id if doctor else 0,
        doctor_name=doctor.full_name if doctor else "Doctor",
        hospital_id=hospital_id,
        total_tokens_issued=session.last_sequence_number,
        waiting_count=len(waiting_tickets),
        consumed_capacity=consumed_count,
        max_capacity=session.max_capacity,
        currently_calling=QueueTicketStaffOut.model_validate(calling_ticket) if calling_ticket else None,
        currently_serving=QueueTicketStaffOut.model_validate(serving_ticket) if serving_ticket else None,
        waiting_tickets=[QueueTicketStaffOut.model_validate(t) for t in waiting_tickets],
    )


@router.post(
    "/{hospital_id}/sessions/{session_id}/queue/call-next",
    response_model=CallNextResponse,
    summary="Advance the queue and call the next waiting patient",
    responses={
        200: {"description": "Next patient called successfully, or queue is empty"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - staff isolation violation"},
        404: {"description": "Hospital or session not found in this hospital"},
        409: {"description": "Conflict - another patient is currently called or in consultation"},
    },
)
def call_next_patient(
    hospital_id: int,
    session_id: int,
    current_user: User = Depends(require_hospital_staff),
    db: Session = Depends(get_db),
):
    """
    Advances the queue by calling the next patient in WAITING status.
    Enforces:
    1. Single-patient-at-a-time rule: Rejects if any ticket is currently CALLING or IN_CONSULTATION.
    2. Empty queue handling: Returns HTTP 200 OK with ticket: None when no waiting patients exist.
    3. Monotonic FIFO order: Calls the ticket with the lowest sequence_number in WAITING status.
    """
    get_hospital_session_or_404(hospital_id, session_id, db)

    # 1. Enforce single patient rule
    active_ticket = db.query(QueueTicket).filter(
        QueueTicket.session_id == session_id,
        QueueTicket.status.in_([TicketStatus.CALLING, TicketStatus.IN_CONSULTATION]),
    ).first()

    if active_ticket:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot call next patient. Ticket {active_ticket.ticket_number} "
                f"({active_ticket.patient_name}) is currently {active_ticket.status.value}. "
                f"Please complete or mark this ticket as no-show before calling the next patient."
            ),
        )

    # 2. Query next waiting ticket in sequence
    next_ticket = db.query(QueueTicket).filter(
        QueueTicket.session_id == session_id,
        QueueTicket.status == TicketStatus.WAITING,
    ).order_by(QueueTicket.sequence_number.asc()).first()

    if not next_ticket:
        return CallNextResponse(
            message="No patients are currently waiting in this session",
            session_id=session_id,
            ticket=None,
        )

    next_ticket.status = TicketStatus.CALLING
    next_ticket.called_at = func.now()
    db.commit()
    db.refresh(next_ticket)

    return CallNextResponse(
        message=f"Ticket {next_ticket.ticket_number} called successfully",
        session_id=session_id,
        ticket=QueueTicketStaffOut.model_validate(next_ticket),
    )


@router.post(
    "/{hospital_id}/sessions/{session_id}/walk-in",
    response_model=TicketActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue an in-person walk-in ticket at the hospital desk",
    responses={
        201: {"description": "Walk-in ticket issued successfully"},
        400: {"description": "Session closed or completed"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - staff isolation violation"},
        404: {"description": "Hospital or session not found in this hospital"},
        409: {"description": "Conflict - session capacity reached"},
    },
)
def issue_walk_in_ticket(
    hospital_id: int,
    session_id: int,
    payload: WalkInTicketRequest,
    current_user: User = Depends(require_hospital_staff),
    db: Session = Depends(get_db),
):
    """
    Issues an in-person walk-in ticket at the registration desk.
    Enforces row-level lock, capacity verification, and monotonic sequence allocation.
    """
    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id,
        ConsultationSession.hospital_id == hospital_id,
    ).with_for_update().first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation session not found in this hospital",
        )

    if session.status == SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consultation session is completed and no longer accepting queue entries",
        )

    doctor = db.query(Doctor).filter(Doctor.id == session.doctor_id).first()
    if not doctor or not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot issue tickets for an inactive doctor",
        )

    # Active capacity check
    if session.max_capacity > 0:
        consumed_count = db.query(QueueTicket).filter(
            QueueTicket.session_id == session.id,
            QueueTicket.status.in_([
                TicketStatus.WAITING,
                TicketStatus.CALLING,
                TicketStatus.IN_CONSULTATION,
                TicketStatus.COMPLETED,
            ]),
        ).count()

        if consumed_count >= session.max_capacity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Consultation session has reached its active capacity limit of {session.max_capacity} patients",
            )

    session.last_sequence_number += 1
    next_sequence = session.last_sequence_number
    prefix = doctor.ticket_prefix or "DR"
    ticket_num = f"{prefix}-{next_sequence:03d}"

    walk_in_ticket = QueueTicket(
        session_id=session.id,
        hospital_id=hospital_id,
        doctor_id=session.doctor_id,
        user_id=None,
        ticket_number=ticket_num,
        sequence_number=next_sequence,
        patient_name=payload.patient_name.strip(),
        patient_phone=payload.patient_phone.strip() if payload.patient_phone else None,
        source=TicketSource.WALK_IN,
        status=TicketStatus.WAITING,
    )

    try:
        db.add(walk_in_ticket)
        db.commit()
        db.refresh(walk_in_ticket)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict allocating walk-in ticket sequence. Please retry.",
        )

    return TicketActionResponse(
        message=f"Walk-in ticket {walk_in_ticket.ticket_number} issued successfully",
        ticket=QueueTicketStaffOut.model_validate(walk_in_ticket),
    )


@router.post(
    "/{hospital_id}/tickets/{ticket_id}/serve",
    response_model=TicketActionResponse,
    summary="Mark a called patient as currently in consultation (CALLING -> IN_CONSULTATION)",
    responses={
        200: {"description": "Patient consultation started"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - staff isolation violation"},
        404: {"description": "Ticket not found in this hospital"},
        409: {"description": "Conflict - ticket not in CALLING status"},
    },
)
def serve_patient(
    hospital_id: int,
    ticket_id: int,
    current_user: User = Depends(require_hospital_staff),
    db: Session = Depends(get_db),
):
    """
    Transitions a ticket from CALLING to IN_CONSULTATION.
    Sets started_at timestamp.
    """
    ticket = db.query(QueueTicket).filter(
        QueueTicket.id == ticket_id,
        QueueTicket.hospital_id == hospital_id,
    ).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue ticket not found in this hospital",
        )

    if ticket.status != TicketStatus.CALLING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot start consultation for a ticket with status '{ticket.status.value}'. Must be in CALLING status.",
        )

    ticket.status = TicketStatus.IN_CONSULTATION
    ticket.started_at = func.now()
    db.commit()
    db.refresh(ticket)

    return TicketActionResponse(
        message=f"Consultation started for ticket {ticket.ticket_number}",
        ticket=QueueTicketStaffOut.model_validate(ticket),
    )


@router.post(
    "/{hospital_id}/tickets/{ticket_id}/complete",
    response_model=TicketActionResponse,
    summary="Mark patient consultation as completed (IN_CONSULTATION -> COMPLETED)",
    responses={
        200: {"description": "Consultation completed successfully"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - staff isolation violation"},
        404: {"description": "Ticket not found in this hospital"},
        409: {"description": "Conflict - ticket not currently in consultation"},
    },
)
def complete_consultation(
    hospital_id: int,
    ticket_id: int,
    current_user: User = Depends(require_hospital_staff),
    db: Session = Depends(get_db),
):
    """
    Transitions a ticket to COMPLETED (terminal state).
    Sets completed_at timestamp.
    Frees the doctor to call the next patient.
    """
    ticket = db.query(QueueTicket).filter(
        QueueTicket.id == ticket_id,
        QueueTicket.hospital_id == hospital_id,
    ).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue ticket not found in this hospital",
        )

    if ticket.status in (TicketStatus.COMPLETED, TicketStatus.CANCELLED, TicketStatus.NO_SHOW):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot complete a ticket that is already {ticket.status.value}",
        )

    if ticket.status != TicketStatus.IN_CONSULTATION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot complete a ticket with status '{ticket.status.value}'. Must be actively in consultation (IN_CONSULTATION status).",
        )

    ticket.status = TicketStatus.COMPLETED
    ticket.completed_at = func.now()
    db.commit()
    db.refresh(ticket)

    return TicketActionResponse(
        message=f"Consultation completed for ticket {ticket.ticket_number}",
        ticket=QueueTicketStaffOut.model_validate(ticket),
    )


@router.post(
    "/{hospital_id}/tickets/{ticket_id}/no-show",
    response_model=TicketActionResponse,
    summary="Mark a non-attending patient as skipped (CALLING -> NO_SHOW)",
    responses={
        200: {"description": "Ticket marked as no-show"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - staff isolation violation"},
        404: {"description": "Ticket not found in this hospital"},
        409: {"description": "Conflict - ticket not currently in CALLING status"},
    },
)
def mark_patient_no_show(
    hospital_id: int,
    ticket_id: int,
    current_user: User = Depends(require_hospital_staff),
    db: Session = Depends(get_db),
):
    """
    Transitions a called patient to NO_SHOW (terminal state).
    Requires the ticket to be in CALLING status.
    Sets completed_at timestamp.
    Frees the doctor to call the next patient.
    NO_SHOW tickets do not consume active capacity.
    """
    ticket = db.query(QueueTicket).filter(
        QueueTicket.id == ticket_id,
        QueueTicket.hospital_id == hospital_id,
    ).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue ticket not found in this hospital",
        )

    if ticket.status in (TicketStatus.COMPLETED, TicketStatus.CANCELLED, TicketStatus.NO_SHOW):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot mark a ticket as no-show when it is already {ticket.status.value}",
        )

    if ticket.status != TicketStatus.CALLING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot mark a ticket as no-show when its status is '{ticket.status.value}'. Must be in CALLING status.",
        )

    ticket.status = TicketStatus.NO_SHOW
    ticket.completed_at = func.now()
    db.commit()
    db.refresh(ticket)

    return TicketActionResponse(
        message=f"Ticket {ticket.ticket_number} marked as no-show",
        ticket=QueueTicketStaffOut.model_validate(ticket),
    )
