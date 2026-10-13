from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import (
    Hospital,
    HospitalStatus,
    Doctor,
    ConsultationSession,
    SessionStatus,
    QueueTicket,
    TicketStatus,
    TicketSource,
    User,
    UserRole,
)
from app.schemas import (
    TicketJoinRequest,
    QueueTicketPatientOut,
    PatientTicketActionResponse,
    LiveQueuePublicStatusOut,
)
from app.dependencies import get_current_user, require_patient

router = APIRouter()


# ============================================================================
# Queue Position & Waiting Time Metric Calculations
# ============================================================================

def compute_queue_metrics(
    ticket: QueueTicket,
    db: Session,
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Computes real-time dynamic queue metrics for a ticket:
    - queue_position: 1-indexed position in WAITING line; 0 if currently being called or served; None if finalized
    - patients_ahead: exact count of waiting patients with sequence_number < ticket.sequence_number
    - estimated_wait_mins: approximate wait time in minutes based on doctor avg consultation duration
    """
    if ticket.status in (TicketStatus.COMPLETED, TicketStatus.CANCELLED, TicketStatus.NO_SHOW):
        return (None, None, None)

    if ticket.status in (TicketStatus.CALLING, TicketStatus.IN_CONSULTATION):
        return (0, 0, 0)

    # Status is WAITING
    patients_ahead = db.query(QueueTicket).filter(
        QueueTicket.session_id == ticket.session_id,
        QueueTicket.status == TicketStatus.WAITING,
        QueueTicket.sequence_number < ticket.sequence_number,
    ).count()

    queue_position = patients_ahead + 1

    active_in_room = db.query(QueueTicket).filter(
        QueueTicket.session_id == ticket.session_id,
        QueueTicket.status.in_([TicketStatus.CALLING, TicketStatus.IN_CONSULTATION]),
    ).count()

    doctor = db.query(Doctor).filter(Doctor.id == ticket.doctor_id).first()
    avg_mins = doctor.avg_consultation_time_mins if (doctor and doctor.avg_consultation_time_mins) else 15

    estimated_wait_mins = (patients_ahead + active_in_room) * avg_mins

    return (queue_position, patients_ahead, estimated_wait_mins)


def build_patient_ticket_out(ticket: QueueTicket, db: Session) -> QueueTicketPatientOut:
    """
    Builds a sanitized patient-facing ticket representation.
    Protects patient privacy by excluding any sensitive third-party details.
    """
    queue_pos, ahead, est_wait = compute_queue_metrics(ticket, db)
    session = db.query(ConsultationSession).filter(ConsultationSession.id == ticket.session_id).first()
    doctor = db.query(Doctor).filter(Doctor.id == ticket.doctor_id).first()
    hospital = db.query(Hospital).filter(Hospital.id == ticket.hospital_id).first()

    return QueueTicketPatientOut(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        sequence_number=ticket.sequence_number,
        patient_name=ticket.patient_name,
        patient_phone=ticket.patient_phone,
        status=ticket.status,
        source=ticket.source,
        session_id=ticket.session_id,
        session_name=session.session_name if session else None,
        doctor_name=doctor.full_name if doctor else None,
        hospital_name=hospital.name if hospital else None,
        queue_position=queue_pos,
        patients_ahead=ahead,
        estimated_wait_mins=est_wait,
        created_at=ticket.created_at,
        called_at=ticket.called_at,
        started_at=ticket.started_at,
        completed_at=ticket.completed_at,
        cancelled_at=ticket.cancelled_at,
    )


# ============================================================================
# Patient Queue Endpoints
# ============================================================================

@router.post(
    "/sessions/{session_id}/tickets",
    response_model=PatientTicketActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join consultation session queue as an authenticated patient",
    responses={
        201: {"description": "Ticket issued successfully"},
        400: {"description": "Session closed, completed, or invalid date"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - reserved for patient accounts"},
        404: {"description": "Hospital, session, or doctor not found"},
        409: {"description": "Conflict - active ticket exists, session full, or paused"},
    },
)
def join_session_queue(
    session_id: int,
    payload: TicketJoinRequest,
    current_patient: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """
    Allows an authenticated patient to join an active OPD consultation session queue.
    Enforces:
    1. Patient-only authorization (Staff/Admin cannot use this online join endpoint).
    2. Atomic row-level lock on ConsultationSession row (SELECT ... FOR UPDATE).
    3. Hospital must be APPROVED and is_accepting_bookings == True.
    4. Doctor must be active and bound to the hospital.
    5. Session date cannot be in the past.
    6. Session must be in SCHEDULED or ACTIVE status (not PAUSED or COMPLETED).
    7. Patient cannot have an existing active ticket (WAITING, CALLING, IN_CONSULTATION) in this session.
    8. Active capacity check: CANCELLED and NO_SHOW tickets do not consume active capacity; COMPLETED and WAITING do.
    9. Atomically increments session.last_sequence_number and guarantees unique token number.
    """
    # 1. Inspect ConsultationSession to identify target hospital
    session_preview = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id
    ).first()

    if not session_preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation session not found",
        )

    # 2. Acquire row-level exclusive lock on Hospital to serialize bookings and prevent
    # concurrent duplicate active tickets at this hospital under MySQL InnoDB
    hospital = db.query(Hospital).filter(
        Hospital.id == session_preview.hospital_id
    ).with_for_update().first()

    if not hospital or hospital.status != HospitalStatus.APPROVED or not hospital.is_accepting_bookings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found or not currently accepting bookings",
        )

    # 3. Acquire row-level exclusive lock on ConsultationSession for sequence number allocation
    session = db.query(ConsultationSession).filter(
        ConsultationSession.id == session_id
    ).with_for_update().first()

    # 4. Doctor validation
    doctor = db.query(Doctor).filter(Doctor.id == session.doctor_id).first()
    if not doctor or doctor.hospital_id != session.hospital_id or not doctor.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found or inactive in this hospital",
        )

    # 5. Session status & date validation
    if session.session_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot join a past consultation session",
        )

    if session.status == SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consultation session is completed and no longer accepting queue entries",
        )

    if session.status == SessionStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Consultation session queue is currently paused",
        )

    # 6. Enforce ONE active ticket per patient per hospital across all doctors and sessions
    # Using with_for_update() guarantees a current locking read of newly committed records
    existing_active = db.query(QueueTicket).filter(
        QueueTicket.hospital_id == session.hospital_id,
        QueueTicket.user_id == current_patient.id,
        QueueTicket.status.in_([TicketStatus.WAITING, TicketStatus.CALLING, TicketStatus.IN_CONSULTATION]),
    ).with_for_update().first()

    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already hold an active queue ticket ({existing_active.ticket_number}) at this hospital",
        )

    # 6. Active capacity check (CANCELLED and NO_SHOW tickets do not consume active capacity)
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

    # 7. Safe monotonic sequence allocation
    session.last_sequence_number += 1
    next_sequence = session.last_sequence_number
    prefix = doctor.ticket_prefix or "DR"
    ticket_num = f"{prefix}-{next_sequence:03d}"

    new_ticket = QueueTicket(
        session_id=session.id,
        hospital_id=session.hospital_id,
        doctor_id=session.doctor_id,
        user_id=current_patient.id,
        ticket_number=ticket_num,
        sequence_number=next_sequence,
        patient_name=payload.patient_name.strip(),
        patient_phone=payload.patient_phone.strip() if payload.patient_phone else None,
        source=TicketSource.ONLINE,
        status=TicketStatus.WAITING,
    )

    try:
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict allocating queue ticket sequence. Please retry.",
        )

    patient_out = build_patient_ticket_out(new_ticket, db)
    return PatientTicketActionResponse(
        message=f"Queue ticket {new_ticket.ticket_number} issued successfully. You are #{patient_out.queue_position} in line.",
        ticket=patient_out,
    )


@router.get(
    "/sessions/{session_id}/queue/status",
    response_model=LiveQueuePublicStatusOut,
    summary="Public anonymized live queue status for lobby displays",
    responses={
        200: {"description": "Anonymized live queue status"},
        404: {"description": "Session not found"},
    },
)
def get_public_queue_status(
    session_id: int,
    db: Session = Depends(get_db),
):
    """
    Public, anonymized queue overview for waiting area screens or prospective patients.
    Strictly excludes any patient names, phone numbers, or user IDs.
    """
    session = db.query(ConsultationSession).filter(ConsultationSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consultation session not found",
        )

    doctor = db.query(Doctor).filter(Doctor.id == session.doctor_id).first()

    calling_ticket = db.query(QueueTicket).filter(
        QueueTicket.session_id == session_id,
        QueueTicket.status == TicketStatus.CALLING,
    ).first()

    serving_ticket = db.query(QueueTicket).filter(
        QueueTicket.session_id == session_id,
        QueueTicket.status == TicketStatus.IN_CONSULTATION,
    ).first()

    waiting_count = db.query(QueueTicket).filter(
        QueueTicket.session_id == session_id,
        QueueTicket.status == TicketStatus.WAITING,
    ).count()

    return LiveQueuePublicStatusOut(
        session_id=session.id,
        session_name=session.session_name,
        session_status=session.status,
        doctor_id=doctor.id if doctor else 0,
        doctor_name=doctor.full_name if doctor else "Doctor",
        currently_calling_token=calling_ticket.ticket_number if calling_ticket else None,
        currently_serving_token=serving_ticket.ticket_number if serving_ticket else None,
        waiting_count=waiting_count,
        total_tokens_issued=session.last_sequence_number,
    )


@router.get(
    "/tickets/my",
    response_model=list[QueueTicketPatientOut],
    summary="List authenticated user's active and historical queue tickets",
    responses={
        200: {"description": "List of patient's own tickets"},
        401: {"description": "Unauthenticated access"},
    },
)
def get_my_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns all queue tickets belonging to the authenticated user,
    with real-time dynamic queue positions and estimated waiting times.
    """
    tickets = db.query(QueueTicket).filter(
        QueueTicket.user_id == current_user.id
    ).order_by(QueueTicket.created_at.desc()).all()

    return [build_patient_ticket_out(t, db) for t in tickets]


@router.get(
    "/tickets/{ticket_id}",
    response_model=QueueTicketPatientOut,
    summary="Retrieve details of a specific queue ticket with live position",
    responses={
        200: {"description": "Queue ticket details"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - access to other patients' tickets is restricted"},
        404: {"description": "Ticket not found"},
    },
)
def get_ticket_details(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves queue ticket details. Enforces strict privacy and ownership:
    - Patients may only view their own tickets.
    - Staff may only view tickets belonging to their assigned hospital.
    - Admins may view any ticket.
    """
    ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue ticket not found",
        )

    if current_user.role == UserRole.PATIENT:
        if ticket.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view your own tickets",
            )
    elif current_user.role == UserRole.STAFF:
        if current_user.hospital_id != ticket.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Staff can only view tickets for their assigned hospital",
            )

    return build_patient_ticket_out(ticket, db)


@router.post(
    "/tickets/{ticket_id}/cancel",
    response_model=PatientTicketActionResponse,
    summary="Cancel an active queue ticket (Self-cancellation or staff)",
    responses={
        200: {"description": "Ticket cancelled successfully"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - ownership or tenant isolation violation"},
        404: {"description": "Ticket not found"},
        409: {"description": "Conflict - ticket already finalized or currently in consultation"},
    },
)
def cancel_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cancels an active queue ticket in WAITING or CALLING status.
    - Patient can cancel only their own tickets.
    - Staff can cancel tickets only within their assigned hospital.
    - IN_CONSULTATION tickets cannot be cancelled.
    - COMPLETED, CANCELLED, and NO_SHOW are terminal and cannot be modified.
    - Cancellation immediately advances subsequent waiting patients' positions and frees active capacity.
    """
    ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue ticket not found",
        )

    if current_user.role == UserRole.PATIENT:
        if ticket.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only cancel your own tickets",
            )
    elif current_user.role == UserRole.STAFF:
        if current_user.hospital_id != ticket.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Staff can only cancel tickets for their assigned hospital",
            )

    if ticket.status in (TicketStatus.COMPLETED, TicketStatus.CANCELLED, TicketStatus.NO_SHOW):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel a ticket that is already {ticket.status.value}",
        )

    if ticket.status == TicketStatus.IN_CONSULTATION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel a ticket that is currently in consultation",
        )

    ticket.status = TicketStatus.CANCELLED
    ticket.cancelled_at = func.now()
    db.commit()
    db.refresh(ticket)

    patient_out = build_patient_ticket_out(ticket, db)
    return PatientTicketActionResponse(
        message=f"Queue ticket {ticket.ticket_number} has been cancelled successfully",
        ticket=patient_out,
    )
