from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.security import verify_password, create_access_token
from app.dependencies import get_current_user

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and issue JWT access token",
    responses={
        401: {"description": "Incorrect email or password"},
    },
)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Validates user credentials against authoritative database records.
    Protects against email enumeration by returning identical generic error messages
    for both non-existent users and incorrect passwords.
    """
    user = db.query(User).filter(User.email == credentials.email).first()

    # Generic error preventing account enumeration attacks
    auth_failure = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        raise auth_failure

    if not verify_password(credentials.password, user.password_hash):
        raise auth_failure

    if not user.is_active:
        raise auth_failure

    # Issue signed JWT token containing role and tenant binding claims
    token_claims = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "hospital_id": user.hospital_id,
    }
    access_token = create_access_token(data=token_claims)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserOut.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="Fetch profile of currently authenticated user",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Protected endpoint that validates the client's Bearer token and
    returns the sanitized current user profile without exposing password hashes.
    """
    return UserOut.model_validate(current_user)
