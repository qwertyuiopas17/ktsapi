"""
KTS — Auth Router

1. Client signs in with Firebase Phone Auth and sends the ID token to POST /auth/firebase.
2. Server verifies it and returns a short-lived access token + 30-day refresh token.
3. POST /auth/refresh rotates the refresh token. Logout revokes one or all sessions.
4. A 4–6 digit PIN gives quick unlock on the device.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import OWNER, RequestContext, allow, get_ctx
from app.models import Business, User
from app.rate_limit import limiter
from app.schemas.auth import (
    BusinessSetupRequest, BusinessSetupResponse, FirebaseLoginRequest, MeResponse,
    RefreshRequest, SetPinRequest, TokenResponse, VerifyPinRequest, VerifyPinResponse,
)
from app.services.auth_service import (
    create_access_token, hash_pin, issue_refresh_token, revoke_all_sessions,
    revoke_refresh_token, rotate_refresh_token, verify_phone_identity, verify_pin,
)
from slowapi.util import get_remote_address

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def _needs_setup(business: Business | None) -> bool:
    return business is None or not business.state_code


def _token_response(db: Session, user: User, *, is_new: bool = False) -> TokenResponse:
    refresh_raw, _ = issue_refresh_token(db, user)
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=refresh_raw,
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
        user_id=str(user.id),
        business_id=str(user.business_id),
        role=user.role,
        is_new_user=is_new,
        needs_business_setup=_needs_setup(db.get(Business, user.business_id)),
    )


@router.post("/firebase", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH, key_func=get_remote_address)
def firebase_login(request: Request, data: FirebaseLoginRequest, db: Session = Depends(get_db)):
    """
    Exchange a Firebase phone-auth ID token for KTS tokens.
    A phone number seen for the first time becomes the owner of a new business;
    staff are invited by an owner first (POST /api/v1/users) and then sign in here.
    """
    identity = verify_phone_identity(data.id_token)

    user = db.query(User).filter(User.phone == identity.phone).first()
    is_new = user is None
    if user is None:
        business = Business(id=uuid.uuid4(), name="My Business", phone=identity.phone)
        db.add(business)
        user = User(
            id=uuid.uuid4(),
            business_id=business.id,
            name="Owner",
            phone=identity.phone,
            role="owner",
            firebase_uid=identity.firebase_uid,
        )
        db.add(user)
        db.flush()
    else:
        if not user.is_active:
            raise HTTPException(status_code=403, detail="This account has been disabled")
        if identity.firebase_uid and user.firebase_uid != identity.firebase_uid:
            user.firebase_uid = identity.firebase_uid

    return _token_response(db, user, is_new=is_new)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH, key_func=get_remote_address)
def refresh(request: Request, data: RefreshRequest, db: Session = Depends(get_db)):
    """Rotate a refresh token. The old one stops working immediately."""
    user, new_refresh = rotate_refresh_token(db, data.refresh_token)
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=new_refresh,
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
        user_id=str(user.id),
        business_id=str(user.business_id),
        role=user.role,
        needs_business_setup=_needs_setup(db.get(Business, user.business_id)),
    )


@router.post("/logout", status_code=204)
def logout(data: RefreshRequest, ctx: RequestContext = Depends(get_ctx), db: Session = Depends(get_db)):
    """Revoke this device's refresh token."""
    revoke_refresh_token(db, data.refresh_token, ctx.user_id)
    db.commit()


@router.post("/logout-all", status_code=204)
def logout_all(ctx: RequestContext = Depends(get_ctx), db: Session = Depends(get_db)):
    """Revoke every session of the current user, on every device."""
    revoke_all_sessions(db, db.get(User, ctx.user_id))
    db.commit()


@router.get("/me", response_model=MeResponse)
def me(ctx: RequestContext = Depends(get_ctx), db: Session = Depends(get_db)):
    user = db.get(User, ctx.user_id)
    business = db.get(Business, ctx.business_id)
    return MeResponse(
        user_id=str(user.id),
        name=user.name,
        phone=user.phone,
        role=user.role,
        business_id=str(business.id),
        business_name=business.name,
        has_pin=user.pin_hash is not None,
        needs_business_setup=_needs_setup(business),
    )


@router.post("/set-pin", status_code=204)
def set_pin(data: SetPinRequest, ctx: RequestContext = Depends(get_ctx), db: Session = Depends(get_db)):
    """Set or change the 4–6 digit quick-unlock PIN."""
    user = db.get(User, ctx.user_id)
    user.pin_hash = hash_pin(data.pin)
    user.pin_failed_attempts = 0
    db.commit()


@router.post("/verify-pin", response_model=VerifyPinResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def check_pin(
    request: Request,
    data: VerifyPinRequest,
    ctx: RequestContext = Depends(get_ctx),
    db: Session = Depends(get_db),
):
    """
    Check the quick-unlock PIN. After PIN_MAX_ATTEMPTS failures every session is
    revoked and the user must sign in with their phone again.
    """
    user = db.get(User, ctx.user_id)
    if not user.pin_hash:
        raise HTTPException(status_code=400, detail="No PIN set")

    if verify_pin(data.pin, user.pin_hash):
        user.pin_failed_attempts = 0
        db.commit()
        return VerifyPinResponse(valid=True, attempts_remaining=settings.PIN_MAX_ATTEMPTS)

    user.pin_failed_attempts = (user.pin_failed_attempts or 0) + 1
    remaining = settings.PIN_MAX_ATTEMPTS - user.pin_failed_attempts
    if remaining <= 0:
        user.pin_failed_attempts = 0
        revoke_all_sessions(db, user)
        db.commit()
        raise HTTPException(status_code=401, detail="Too many wrong PINs. Please sign in again.")
    db.commit()
    return VerifyPinResponse(valid=False, attempts_remaining=remaining)


@router.put("/business", response_model=BusinessSetupResponse)
def setup_business(
    data: BusinessSetupRequest,
    ctx: RequestContext = Depends(allow(*OWNER)),
    db: Session = Depends(get_db),
):
    """Complete or update the business profile of the signed-in owner."""
    business = db.get(Business, ctx.business_id)
    for key, value in data.model_dump().items():
        setattr(business, key, value)
    db.commit()
    return BusinessSetupResponse(business_id=str(business.id))
