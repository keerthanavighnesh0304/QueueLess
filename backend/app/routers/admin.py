from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Hospital, HospitalStatus, User
from app.schemas import HospitalOut, HospitalActionResponse
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
