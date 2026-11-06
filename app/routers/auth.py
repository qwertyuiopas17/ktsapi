"""
KTS — Auth Router
Phone OTP → verify → JWT token → PIN setup → business setup.
Uses Firebase Auth for OTP under the hood.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt
from passlib.hash import bcrypt
import uuid

from app.database import get_db
from app.config import settings
from app.models import User, Business
from app.schemas.auth import (
    SendOtpRequest, SendOtpResponse,
    VerifyOtpRequest, VerifyOtpResponse,
    SetPinRequest, VerifyPinRequest,
    BusinessSetupRequest, BusinessSetupResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, business_id: str | None = None) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": user_id,
        "business_id": business_id,
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def get_current_user(db: Session = Depends(get_db)):
    """
    Dependency — extracts and validates the current user from JWT.
    For now, returns a mock user for development. Wire Firebase in production.
    """
    # TODO: Extract token from Authorization header, verify JWT, fetch user
    # For development, we'll use a header-based user_id
    pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/send-otp", response_model=SendOtpResponse)
def send_otp(request: SendOtpRequest):
    """
    Step 1: Send OTP to phone number via Firebase.
    In dev mode, returns a mock session_id.
    """
    # TODO: Integrate Firebase Admin SDK — admin.auth().create_session_cookie()
    # For now, mock it for development
    return SendOtpResponse(
        message="OTP sent successfully",
        session_id=f"dev-session-{uuid.uuid4().hex[:8]}",
    )


@router.post("/verify-otp", response_model=VerifyOtpResponse)
def verify_otp(request: VerifyOtpRequest, db: Session = Depends(get_db)):
    """
    Step 2: Verify OTP → create or fetch user → return JWT.
    """
    # TODO: Verify OTP with Firebase — admin.auth().verify_id_token()
    # For development, accept any 6-digit OTP
    if len(request.otp) != 6:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Check if user exists
    user = db.query(User).filter(User.phone == request.phone).first()
    is_new = user is None
    has_business = False

    if is_new:
        # Create new user (without business — that comes next)
        user = User(
            id=uuid.uuid4(),
            business_id=uuid.uuid4(),  # placeholder, will be updated in business setup
            name="New User",
            phone=request.phone,
            role="owner",
        )
        # We need a business first — create a placeholder
        placeholder_biz = Business(
            id=user.business_id,
            name="My Business",
        )
        db.add(placeholder_biz)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        has_business = user.business is not None and user.business.name != "My Business"

    token = create_access_token(
        user_id=str(user.id),
        business_id=str(user.business_id),
    )

    return VerifyOtpResponse(
        access_token=token,
        user_id=str(user.id),
        is_new_user=is_new,
        has_business=has_business,
    )


@router.post("/set-pin")
def set_pin(request: SetPinRequest, db: Session = Depends(get_db)):
    """
    Step 3: Set a 4-6 digit PIN for quick app unlock.
    """
    # TODO: Extract user from JWT
    # For now, require user_id as query param for dev
    # In production: user = get_current_user()
    raise HTTPException(status_code=501, detail="Wire after Firebase integration")


@router.post("/setup-business", response_model=BusinessSetupResponse)
def setup_business(request: BusinessSetupRequest, db: Session = Depends(get_db)):
    """
    Step 4: Complete business setup (name, GSTIN, state, etc.)
    Called once after first login.
    """
    # TODO: Get user from JWT and update their business
    # For development: create standalone
    business = Business(
        id=uuid.uuid4(),
        name=request.name,
        gstin=request.gstin,
        state_code=request.state_code,
        address=request.address,
        phone=request.phone,
        upi_id=request.upi_id,
        bill_prefix=request.bill_prefix,
    )
    db.add(business)
    db.commit()

    return BusinessSetupResponse(business_id=str(business.id))
