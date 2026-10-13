import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Hospital, HospitalStatus, User, UserRole
from app.schemas import (
    HospitalOut,
    HospitalActionResponse,
    StaffProvisionRequest,
    StaffProvisionResponse,
    UserOut,
)
from app.security import hash_password
from app.dependencies import require_admin

router = APIRouter()


@router.get(
    "/hospitals/pending",
    response_model=list[HospitalOut],
    summary="List all hospitals pending administrative approval",
    responses={
        200: {"description": "List of pending hospital applications"},
        401: {"description": "Unauthenticated access"},
        403: {"description": "Forbidden - administrative privileges required"},
    },
)
def list_pending_hospitals(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Returns all hospital applications currently awaiting administrative review,
    ordered chronologically by creation timestamp.
    """
    pending = db.query(Hospital).filter(
        Hospital.status == HospitalStatus.PENDING_APPROVAL
    ).order_by(Hospital.created_at.asc()).all()

    return pending


@router.post(
    "/hospitals/{hospital_id}/approve",
    response_model=HospitalActionResponse,
    summary="Approve a pending hospital onboarding application",
    responses={
        200: {"description": "Hospital approved and bookings enabled"},
        404: {"description": "Hospital not found"},
        409: {"description": "Conflict - hospital is already approved, rejected, or suspended"},
        403: {"description": "Forbidden - administrative privileges required"},
    },
)
def approve_hospital(
    hospital_id: int,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Approves a pending hospital application and enables patient booking eligibility.
    Rejects invalid state transitions for already processed or suspended facilities.
    """
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()

    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )

    if hospital.status == HospitalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hospital is already approved.",
        )

    if hospital.status == HospitalStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot approve a rejected hospital application.",
        )

    if hospital.status == HospitalStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot approve a suspended hospital through this endpoint.",
        )

    # Valid transition: PENDING_APPROVAL -> APPROVED
    hospital.status = HospitalStatus.APPROVED
    hospital.is_accepting_bookings = True
    db.commit()
    db.refresh(hospital)

    return HospitalActionResponse(
        message="Hospital approved successfully and is now active for bookings",
        hospital=HospitalOut.model_validate(hospital),
    )


@router.post(
    "/hospitals/{hospital_id}/reject",
    response_model=HospitalActionResponse,
    summary="Reject a pending hospital onboarding application",
    responses={
        200: {"description": "Hospital application rejected and bookings disabled"},
        404: {"description": "Hospital not found"},
        409: {"description": "Conflict - hospital is already rejected, approved, or suspended"},
        403: {"description": "Forbidden - administrative privileges required"},
    },
)
def reject_hospital(
    hospital_id: int,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Rejects a pending hospital application and ensures bookings remain disabled.
    Rejects invalid state transitions for already approved or suspended facilities.
    """
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()

    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found",
        )

    if hospital.status == HospitalStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hospital application is already rejected.",
        )

    if hospital.status == HospitalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reject an already approved active hospital.",
        )

    if hospital.status == HospitalStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reject a suspended hospital.",
        )

    # Valid transition: PENDING_APPROVAL -> REJECTED
    hospital.status = HospitalStatus.REJECTED
    hospital.is_accepting_bookings = False
    db.commit()
    db.refresh(hospital)

    return HospitalActionResponse(
        message="Hospital application rejected",
        hospital=HospitalOut.model_validate(hospital),
    )


@router.post(
    "/hospitals/{hospital_id}/provision-staff",
    response_model=StaffProvisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision the first or initial manager/staff account for an approved hospital (Admin only)",
    responses={
        201: {"description": "Staff account provisioned successfully"},
        400: {"description": "Hospital is not approved or invalid input"},
        403: {"description": "Forbidden - administrative privileges required"},
        404: {"description": "Hospital not found"},
        409: {"description": "A user with this email already exists"},
    },
)
def provision_hospital_staff(
    hospital_id: int,
    payload: StaffProvisionRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Provisions a staff/manager account bound strictly to an approved hospital.
    Reuses UserRole.STAFF and User.hospital_id without schema changes.
    Generates a secure temporary password if an initial password is not explicitly supplied.
    The temporary password is only returned in this protected response and is never stored in plaintext or logged.
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
            detail=f"Cannot provision staff for a hospital with status '{hospital.status.value}'. Hospital must be APPROVED first.",
        )

    clean_email = payload.email.lower().strip()
    if "@" not in clean_email or len(clean_email) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid email address is required",
        )

    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{clean_email}' already exists.",
        )

    raw_password = payload.initial_password or secrets.token_urlsafe(12)
    hashed_password = hash_password(raw_password)

    staff_user = User(
        email=clean_email,
        password_hash=hashed_password,
        full_name=payload.full_name.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        role=UserRole.STAFF,
        hospital_id=hospital.id,
        is_active=True,
    )
    db.add(staff_user)
    db.commit()
    db.refresh(staff_user)

    return StaffProvisionResponse(
        message=f"Staff account for '{hospital.name}' provisioned successfully",
        user=UserOut.model_validate(staff_user),
        temporary_password=raw_password,
    )
