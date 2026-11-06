"""Tenant-scoped lookups. Never query a tenant table by id alone."""
from __future__ import annotations

import uuid
from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestContext

T = TypeVar("T")


def get_owned(
    db: Session,
    model: type[T],
    obj_id: uuid.UUID,
    ctx: RequestContext,
    *,
    detail: str | None = None,
    for_update: bool = False,
) -> T:
    """Fetch `model` by id within the caller's business, or raise 404.

    Objects belonging to another business are reported as 404 (not 403) so ids
    cannot be probed across tenants.
    """
    query = db.query(model).filter(model.id == obj_id, model.business_id == ctx.business_id)
    if for_update:
        query = query.with_for_update()
    obj = query.first()
    if obj is None:
        raise HTTPException(status_code=404, detail=detail or f"{model.__name__} not found")
    return obj
