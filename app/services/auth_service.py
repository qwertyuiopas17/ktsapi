"""
KTS — Authentication service

- Access tokens: short-lived HS256 JWTs carrying sub (user id), business_id,
  role and ver (the user's token_version, used for server-side revocation).
- Refresh tokens: opaque random strings, 30 days, rotated on every use. Only a
  SHA-256 hash is stored. Re-using a rotated token revokes every session of
  that user (theft detection).
- Phone identity comes from a Firebase ID token verified server-side.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import RefreshToken, User


def _utcnow() -> datetime:
    # Naive UTC, matching the DateTime columns in the models
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


# ─── PIN ─────────────────────────────────────────────────────
def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, pin_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pin.encode(), pin_hash.encode())
    except ValueError:
        return False


# ─── Access tokens ───────────────────────────────────────────
def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "business_id": str(user.business_id),
        "role": user.role,
        "ver": user.token_version or 0,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Returns the verified payload, or None if the token is invalid/expired."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


# ─── Refresh tokens ──────────────────────────────────────────
def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_refresh_token(db: Session, user: User) -> tuple[str, RefreshToken]:
    raw = secrets.token_urlsafe(48)
    row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=_hash_token(raw),
        token_version=user.token_version or 0,
        expires_at=_utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRY_DAYS),
    )
    db.add(row)
    return raw, row


def rotate_refresh_token(db: Session, raw: str) -> tuple[User, str]:
    """Validate a refresh token, revoke it and issue its replacement."""
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash_token(raw))
        .with_for_update()
        .first()
    )
    if row is None:
        raise _unauthorized("Invalid refresh token")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Account disabled")

    if row.revoked_at is not None:
        if row.replaced_by_id is not None:
            # A rotated token was presented again: assume it leaked and end every session.
            revoke_all_sessions(db, user)
            db.commit()
            raise _unauthorized("Refresh token reuse detected; all sessions revoked")
        raise _unauthorized("Refresh token revoked")

    if row.expires_at < _utcnow() or row.token_version != (user.token_version or 0):
        raise _unauthorized("Refresh token expired")

    new_raw, new_row = issue_refresh_token(db, user)
    row.revoked_at = _utcnow()
    row.replaced_by_id = new_row.id
    return user, new_raw


def revoke_refresh_token(db: Session, raw: str, user_id: uuid.UUID) -> None:
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash_token(raw), RefreshToken.user_id == user_id)
        .first()
    )
    if row is not None and row.revoked_at is None:
        row.revoked_at = _utcnow()


def revoke_all_sessions(db: Session, user: User) -> None:
    """Invalidates all access tokens (via token_version) and refresh tokens."""
    user.token_version = (user.token_version or 0) + 1
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    ).update({RefreshToken.revoked_at: _utcnow()}, synchronize_session=False)


# ─── Firebase phone identity ─────────────────────────────────
@dataclass
class PhoneIdentity:
    phone: str
    firebase_uid: str | None


_firebase_app = None


def _get_firebase_app():
    global _firebase_app
    if _firebase_app is None:
        import firebase_admin
        from firebase_admin import credentials

        options = {"projectId": settings.FIREBASE_PROJECT_ID} if settings.FIREBASE_PROJECT_ID else None
        try:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        except (FileNotFoundError, ValueError):
            cred = credentials.ApplicationDefault()
        _firebase_app = firebase_admin.initialize_app(cred, options)
    return _firebase_app


def verify_phone_identity(id_token: str) -> PhoneIdentity:
    """
    Verify a Firebase ID token issued after Firebase Phone Auth on the client.
    In development/test with AUTH_DEV_STUB=true, "dev:+919876543210" is accepted.
    """
    if settings.AUTH_DEV_STUB and not settings.is_production_like and id_token.startswith("dev:"):
        phone = id_token[4:]
        if not phone.startswith("+") or not phone[1:].isdigit() or not 10 <= len(phone) <= 15:
            raise _unauthorized("Dev token must look like dev:+919876543210")
        return PhoneIdentity(phone=phone, firebase_uid=None)

    try:
        from firebase_admin import auth as fb_auth

        decoded = fb_auth.verify_id_token(id_token, app=_get_firebase_app(), check_revoked=True)
    except ImportError as exc:  # pragma: no cover - deployment misconfiguration
        raise HTTPException(status_code=503, detail="Phone auth is not configured") from exc
    except Exception as exc:
        raise _unauthorized("Invalid or expired phone verification") from exc

    phone = decoded.get("phone_number")
    if not phone:
        raise _unauthorized("Token has no verified phone number")
    return PhoneIdentity(phone=phone, firebase_uid=decoded.get("uid"))
