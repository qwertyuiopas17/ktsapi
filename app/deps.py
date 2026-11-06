"""
KTS — Request context and role-based access dependencies.

Every tenant-scoped endpoint takes `ctx: RequestContext = Depends(allow(...))`
and must filter every query by `ctx.business_id`.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.auth_service import decode_access_token

_bearer = HTTPBearer(auto_error=False)

# Role matrix (Phase 1)
#   owner      — everything
#   accountant — everything except users and business settings
#   manager    — day-to-day operations, but cannot delete or cancel
#   delivery   — read bills/customers, record customer collections
#   warehouse  — products (read) and stock only
OWNER = ("owner",)
ADMIN = ("owner", "accountant")              # deletes, cancellations
OPS = ("owner", "accountant", "manager")     # create/update business documents
FIELD = OPS + ("delivery",)                  # bills, customers, collections (read)
STOCK = ("owner", "accountant", "manager", "warehouse")
STOCK_ADJUST = ("owner", "warehouse")
ALL_ROLES = ("owner", "accountant", "manager", "delivery", "warehouse")


@dataclass(frozen=True)
class RequestContext:
    user_id: uuid.UUID
    business_id: uuid.UUID
    role: str
    phone: str


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_ctx(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> RequestContext:
    """Authenticate the bearer token and load the user's tenant context."""
    if credentials is None:
        raise _unauthorized("Not authenticated. Please log in.")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise _unauthorized("Invalid or expired token. Please log in again.")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise _unauthorized("Invalid token subject") from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Account disabled")
    # Role and business always come from the database, so changes apply immediately;
    # token_version lets us revoke outstanding tokens.
    if payload.get("ver", 0) != (user.token_version or 0):
        raise _unauthorized("Session revoked. Please log in again.")

    return RequestContext(
        user_id=user.id, business_id=user.business_id, role=user.role, phone=user.phone
    )


def allow(*roles: str):
    """Dependency factory: authenticated context restricted to `roles`."""
    allowed = frozenset(roles)

    def _dep(ctx: RequestContext = Depends(get_ctx)) -> RequestContext:
        if ctx.role not in allowed:
            raise HTTPException(status_code=403, detail="Your role cannot perform this action")
        return ctx

    return _dep
