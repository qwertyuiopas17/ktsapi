"""
KTS — JWT Auth Dependencies
Ported from aethel-backend-v3/auth.py with adaptations for KTS:
  - Phone-based auth (not email/password)
  - UUID user IDs (not integer)
  - Business context (multi-tenant)

Uses PyJWT for stateless token encoding.
Tokens carry: sub (user_id), business_id, phone, role.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID

try:
    import jwt
except ImportError:
    print("[KTS Auth] WARNING: PyJWT not installed. Run: pip install PyJWT", file=sys.stderr)
    jwt = None  # type: ignore

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

# ─── Config ──────────────────────────────────────────────────
_JWT_SECRET = settings.JWT_SECRET_KEY
_JWT_ALGORITHM = settings.JWT_ALGORITHM
_JWT_EXPIRY_MINUTES = settings.JWT_EXPIRY_MINUTES

_bearer_scheme = HTTPBearer(auto_error=False)


# ─── Token helpers ────────────────────────────────────────────
def create_token(user_id: str, business_id: str, phone: str, role: str = "owner") -> str:
    """
    Create a signed JWT access token.
    Payload: sub (user_id), business_id, phone, role, exp, iat.
    """
    if jwt is None:
        raise RuntimeError("PyJWT library not installed")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "business_id": str(business_id),
        "phone": phone,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=_JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """
    Decode and validate a JWT. Returns payload dict or None on failure.
    Raises nothing — caller must check for None.
    """
    if jwt is None:
        return None
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        return payload
    except Exception:
        return None


# ─── FastAPI dependencies ─────────────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
):
    """
    FastAPI dependency. Extracts and validates the Bearer token.
    Returns a dict with user_id, business_id, phone, role.
    Raises HTTP 401 on missing/invalid token.

    Pattern from: aethel-backend-v3/auth.py
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": UUID(payload["sub"]),
        "business_id": UUID(payload["business_id"]),
        "phone": payload.get("phone", ""),
        "role": payload.get("role", "owner"),
    }


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
):
    """
    Like get_current_user but does NOT raise on missing token.
    Returns user dict or None. Use on endpoints that work for both
    authenticated and anonymous users (e.g. /health).

    Pattern from: aethel-backend-v3/auth.py
    """
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if payload is None:
        return None
    return {
        "user_id": UUID(payload["sub"]),
        "business_id": UUID(payload["business_id"]),
        "phone": payload.get("phone", ""),
        "role": payload.get("role", "owner"),
    }
