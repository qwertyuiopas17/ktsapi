"""
KTS — Expense Router
Track daily business expenses: fuel, salary, rent, transport, etc.
Feeds directly into the P&L dashboard (PRD §3.8).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from decimal import Decimal
from datetime import date, timedelta
import uuid

from app.database import get_db
from app.deps import ADMIN, OPS, RequestContext, allow
from app.models import Expense
from app.schemas.transactions import (
    ExpenseCreate, ExpenseResponse, ExpenseListResponse, ExpenseSummaryResponse,
)

router = APIRouter(prefix="/api/v1/expenses", tags=["Expenses"])

VALID_CATEGORIES = {
    "fuel", "salary", "rent", "transport", "packaging",
    "damage_waste", "electricity", "phone", "misc",
}
VALID_PAYMENT_MODES = {"cash", "upi", "bank_transfer"}


@router.post("", response_model=ExpenseResponse, status_code=201)
def create_expense(data: ExpenseCreate, ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    """
    Record a business expense.

    Categories: fuel, salary, rent, transport, packaging,
    damage_waste, electricity, phone, misc.
    """
    if data.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{data.category}'. Valid: {sorted(VALID_CATEGORIES)}"
        )
    if data.payment_mode not in VALID_PAYMENT_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment_mode '{data.payment_mode}'. Valid: {sorted(VALID_PAYMENT_MODES)}"
        )

    expense = Expense(
        id=uuid.uuid4(),
        business_id=ctx.business_id,
        category=data.category,
        amount=data.amount,
        expense_date=data.expense_date or date.today(),
        payment_mode=data.payment_mode,
        note=data.note,
        receipt_url=data.receipt_url,
        is_recurring=data.is_recurring,
        created_by=ctx.user_id,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("", response_model=ExpenseListResponse)
def list_expenses(
    category: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: RequestContext = Depends(allow(*OPS)),
    db: Session = Depends(get_db),
):
    """List expenses with filters. Returns total_amount for the filtered set."""
    query = db.query(Expense).filter(Expense.business_id == ctx.business_id)

    if category:
        query = query.filter(Expense.category == category)
    if date_from:
        query = query.filter(Expense.expense_date >= date_from)
    if date_to:
        query = query.filter(Expense.expense_date <= date_to)

    total = query.count()

    # Calculate total amount for the filtered query
    total_amount = db.query(
        sa_func.coalesce(sa_func.sum(Expense.amount), 0)
    ).filter(Expense.business_id == ctx.business_id)

    if category:
        total_amount = total_amount.filter(Expense.category == category)
    if date_from:
        total_amount = total_amount.filter(Expense.expense_date >= date_from)
    if date_to:
        total_amount = total_amount.filter(Expense.expense_date <= date_to)

    amount = total_amount.scalar() or Decimal("0")

    expenses = query.order_by(Expense.expense_date.desc(), Expense.created_at.desc()).offset(skip).limit(limit).all()

    return ExpenseListResponse(
        expenses=[ExpenseResponse.model_validate(e) for e in expenses],
        total=total,
        total_amount=amount,
    )


@router.get("/summary", response_model=ExpenseSummaryResponse)
def expense_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days to summarize"),
    ctx: RequestContext = Depends(allow(*OPS)),
    db: Session = Depends(get_db),
):
    """
    Category-wise expense breakdown for the last N days.
    Perfect for the P&L dashboard pie chart.
    """
    period_end = date.today()
    period_start = period_end - timedelta(days=days)

    rows = (
        db.query(Expense.category, sa_func.sum(Expense.amount))
        .filter(
            Expense.business_id == ctx.business_id,
            Expense.expense_date >= period_start,
            Expense.expense_date <= period_end,
        )
        .group_by(Expense.category)
        .all()
    )

    by_category = {cat: Decimal(str(amt)) for cat, amt in rows}
    total = sum(by_category.values(), Decimal("0"))

    return ExpenseSummaryResponse(
        period_start=period_start,
        period_end=period_end,
        total=total,
        by_category=by_category,
    )


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(expense_id: uuid.UUID, ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    """Get a single expense."""
    expense = db.query(Expense).filter(
        Expense.id == expense_id, Expense.business_id == ctx.business_id
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: uuid.UUID, ctx: RequestContext = Depends(allow(*ADMIN)), db: Session = Depends(get_db)):
    """Delete an expense entry."""
    expense = db.query(Expense).filter(
        Expense.id == expense_id, Expense.business_id == ctx.business_id
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()
