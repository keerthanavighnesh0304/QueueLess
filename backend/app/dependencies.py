from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt, ExpiredSignatureError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, UserRole

# HTTP Bearer scheme extraction
security_bearer = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts and validates the JWT Bearer token from the
    Authorization header, queries the authoritative user record, and verifies account activity.
    Raises HTTP 401 Unauthorized for missing, expired, or invalid tokens.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Enforces that the authenticated user possesses the ADMIN role.
    Raises HTTP 403 Forbidden for patients and staff.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required",
        )
    return current_user


def require_hospital_staff(
    hospital_id: int,
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Enforces hospital-level data isolation for staff operations.
    - Admins have global access to all hospitals.
    - Staff members can ONLY manage their assigned hospital (current_user.hospital_id == hospital_id).
    - Patients or unassigned staff are denied with HTTP 403 Forbidden.
    """
    if current_user.role == UserRole.ADMIN:
        return current_user

    if current_user.role == UserRole.STAFF:
        if current_user.hospital_id is None or current_user.hospital_id != hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: staff members can only manage their assigned hospital",
            )
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Staff or administrative privileges required",
    )


def require_patient(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Enforces that the authenticated user possesses the PATIENT role.
    Raises HTTP 403 Forbidden for staff and admin users attempting online patient queue booking.
    """
    if current_user.role != UserRole.PATIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Online queue joining is reserved for patient accounts. Hospital staff must use the desk walk-in endpoint.",
        )
    return current_user
