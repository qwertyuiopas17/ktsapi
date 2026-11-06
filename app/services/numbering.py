"""
KTS — Financial-year document numbering.

Numbers look like INV/2627/00042 (prefix ≤5 chars, FY April–March, ≤16 chars
as GST requires). Each (business, doc type, FY) series is a row locked with
SELECT ... FOR UPDATE while issuing, so numbers are unique and gap-free: the
counter only advances when the surrounding transaction commits.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Business, DocumentSeries

DEFAULT_PREFIXES = {"credit_note": "CN", "challan": "DC", "receipt": "RCT"}
MAX_LEN = 16


def financial_year(d: date) -> str:
    """FY code for a date: 2026-04-01 .. 2027-03-31 -> "2627"."""
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def _lock_series(db: Session, business_id: uuid.UUID, doc_type: str, fy: str) -> DocumentSeries | None:
    db.flush()
    return (
        db.query(DocumentSeries)
        .filter(
            DocumentSeries.business_id == business_id,
            DocumentSeries.doc_type == doc_type,
            DocumentSeries.fy == fy,
        )
        .with_for_update()
        .populate_existing()
        .first()
    )


def next_document_number(db: Session, business: Business, doc_type: str, on_date: date) -> str:
    fy = financial_year(on_date)
    series = _lock_series(db, business.id, doc_type, fy)
    if series is None:
        prefix = business.bill_prefix if doc_type == "invoice" else DEFAULT_PREFIXES[doc_type]
        try:
            with db.begin_nested():
                series = DocumentSeries(
                    id=uuid.uuid4(), business_id=business.id, doc_type=doc_type,
                    fy=fy, prefix=(prefix or "INV")[:5], next_number=1,
                )
                db.add(series)
        except IntegrityError:
            # Another request created the series first; wait for its lock.
            series = _lock_series(db, business.id, doc_type, fy)

    number = f"{series.prefix}/{fy}/{series.next_number:05d}"
    if len(number) > MAX_LEN:
        raise HTTPException(status_code=409, detail="Document series exhausted for this financial year")
    series.next_number += 1
    db.flush()
    return number
