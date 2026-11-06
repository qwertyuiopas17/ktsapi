"""
KTS — Payment, Ledger, Inventory, and Dashboard Routers
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal
from datetime import date
import uuid

from app.database import get_db
from app.models import (
    Payment, LedgerEntry, Customer, Company,
    Inventory, InventoryTxn, Product, Bill, Purchase, Expense, Business,
)
from app.schemas.transactions import (
    PaymentCreate, PaymentResponse, PaymentListResponse,
    PartyLedgerResponse, LedgerEntryResponse, OutstandingResponse,
    StockDashboardResponse, StockItem, StockAdjustRequest,
    InventoryTxnResponse, DashboardResponse,
)
from app.services.inventory_service import adjust_stock

BUSINESS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# ===========================================================================
# PAYMENTS
# ===========================================================================
payment_router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@payment_router.post("", response_model=PaymentResponse, status_code=201)
def record_payment(data: PaymentCreate, db: Session = Depends(get_db)):
    """
    Record a payment received from customer or made to supplier.
    Updates outstanding balance + creates ledger entry.
    """
    payment_date = data.payment_date or date.today()

    # Get party name
    party_name = None
    if data.party_type == "customer":
        party = db.query(Customer).filter(Customer.id == data.party_id).first()
        if not party:
            raise HTTPException(status_code=404, detail="Customer not found")
        party.outstanding -= data.amount  # reduce outstanding
        if party.outstanding < 0:
            party.outstanding = Decimal("0")
        entry_type = "payment_in"
        party_name = party.name
    elif data.party_type == "company":
        party = db.query(Company).filter(Company.id == data.party_id).first()
        if not party:
            raise HTTPException(status_code=404, detail="Company not found")
        party.outstanding -= data.amount
        if party.outstanding < 0:
            party.outstanding = Decimal("0")
        entry_type = "payment_out"
        party_name = party.name
    else:
        raise HTTPException(status_code=400, detail="party_type must be 'customer' or 'company'")

    payment = Payment(
        id=uuid.uuid4(),
        business_id=BUSINESS_ID,
        party_type=data.party_type,
        party_id=data.party_id,
        amount=data.amount,
        payment_mode=data.payment_mode,
        payment_date=payment_date,
        reference=data.reference,
        note=data.note,
    )
    db.add(payment)

    # Ledger entry
    ledger = LedgerEntry(
        id=uuid.uuid4(),
        business_id=BUSINESS_ID,
        party_type=data.party_type,
        party_id=data.party_id,
        entry_type=entry_type,
        amount=data.amount,
        running_balance=party.outstanding,
        reference_type="payment",
        reference_id=payment.id,
        description=f"Payment {'from' if data.party_type == 'customer' else 'to'} {party_name} ({data.payment_mode})",
    )
    db.add(ledger)

    db.commit()
    db.refresh(payment)

    return PaymentResponse(
        id=payment.id,
        party_type=payment.party_type,
        party_id=payment.party_id,
        party_name=party_name,
        amount=payment.amount,
        payment_mode=payment.payment_mode,
        payment_date=payment.payment_date,
        reference=payment.reference,
        note=payment.note,
        created_at=payment.created_at,
    )


@payment_router.get("", response_model=PaymentListResponse)
def list_payments(
    party_type: str | None = Query(None),
    party_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Payment).filter(Payment.business_id == BUSINESS_ID)
    if party_type:
        query = query.filter(Payment.party_type == party_type)
    if party_id:
        query = query.filter(Payment.party_id == party_id)

    total = query.count()
    payments = query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()

    results = []
    for p in payments:
        name = None
        if p.party_type == "customer":
            c = db.query(Customer).filter(Customer.id == p.party_id).first()
            name = c.name if c else None
        elif p.party_type == "company":
            c = db.query(Company).filter(Company.id == p.party_id).first()
            name = c.name if c else None
        results.append(PaymentResponse(
            id=p.id, party_type=p.party_type, party_id=p.party_id,
            party_name=name, amount=p.amount, payment_mode=p.payment_mode,
            payment_date=p.payment_date, reference=p.reference,
            note=p.note, created_at=p.created_at,
        ))

    return PaymentListResponse(payments=results, total=total)


# ===========================================================================
# LEDGER
# ===========================================================================
ledger_router = APIRouter(prefix="/api/v1/ledger", tags=["Ledger"])


@ledger_router.get("/{party_type}/{party_id}", response_model=PartyLedgerResponse)
def get_party_ledger(
    party_type: str,
    party_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get full ledger for a customer or company (the Splitwise view)."""
    if party_type == "customer":
        party = db.query(Customer).filter(Customer.id == party_id).first()
    elif party_type == "company":
        party = db.query(Company).filter(Company.id == party_id).first()
    else:
        raise HTTPException(status_code=400, detail="party_type must be 'customer' or 'company'")

    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    entries = db.query(LedgerEntry).filter(
        LedgerEntry.party_type == party_type,
        LedgerEntry.party_id == party_id,
    ).order_by(LedgerEntry.created_at.desc()).limit(100).all()

    return PartyLedgerResponse(
        party_type=party_type,
        party_id=party_id,
        party_name=party.name,
        outstanding=party.outstanding,
        entries=[LedgerEntryResponse.model_validate(e) for e in entries],
    )


@ledger_router.get("/outstanding", response_model=OutstandingResponse)
def get_outstanding(db: Session = Depends(get_db)):
    """Outstanding dashboard — total receivable, payable, net."""
    total_receivable = db.query(func.coalesce(func.sum(Customer.outstanding), 0)).filter(
        Customer.business_id == BUSINESS_ID
    ).scalar()

    total_payable = db.query(func.coalesce(func.sum(Company.outstanding), 0)).filter(
        Company.business_id == BUSINESS_ID
    ).scalar()

    # Top overdue customers
    top_customers = db.query(Customer).filter(
        Customer.business_id == BUSINESS_ID,
        Customer.outstanding > 0,
    ).order_by(Customer.outstanding.desc()).limit(5).all()

    return OutstandingResponse(
        total_receivable=Decimal(str(total_receivable)),
        total_payable=Decimal(str(total_payable)),
        net_position=Decimal(str(total_receivable)) - Decimal(str(total_payable)),
        top_overdue_customers=[
            {"name": c.name, "outstanding": float(c.outstanding), "phone": c.phone}
            for c in top_customers
        ],
    )


# ===========================================================================
# INVENTORY
# ===========================================================================
inventory_router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory"])


@inventory_router.get("", response_model=StockDashboardResponse)
def stock_dashboard(
    low_stock_only: bool = Query(False),
    category: str | None = Query(None),
    sort_by: str = Query("name", description="name, stock_level, category"),
    db: Session = Depends(get_db),
):
    """
    The headline screen — 'never walk the godown again'.
    Shows all products with live stock levels and status.
    """
    query = db.query(Product, Inventory).outerjoin(
        Inventory, Inventory.product_id == Product.id
    ).filter(
        Product.business_id == BUSINESS_ID,
        Product.is_active == True,
    )

    if category:
        query = query.filter(Product.category == category)

    results = query.all()

    items = []
    total_value = Decimal("0")
    low_count = 0
    out_count = 0

    for product, inv in results:
        qty_primary = inv.qty_primary if inv else Decimal("0")
        qty_secondary = qty_primary * product.conversion_factor
        stock_value = qty_primary * product.purchase_price

        if qty_primary <= 0:
            status = "out"
            out_count += 1
        elif qty_primary <= product.low_stock_threshold:
            status = "low"
            low_count += 1
        else:
            status = "ok"

        if low_stock_only and status == "ok":
            continue

        items.append(StockItem(
            product_id=product.id,
            product_name=product.name,
            shortcode=product.shortcode,
            category=product.category,
            qty_primary=qty_primary,
            qty_secondary=qty_secondary,
            primary_unit=product.primary_unit,
            secondary_unit=product.secondary_unit,
            stock_value=stock_value,
            low_stock_threshold=product.low_stock_threshold,
            status=status,
        ))
        total_value += stock_value

    # Sort
    if sort_by == "stock_level":
        items.sort(key=lambda x: x.qty_primary)
    elif sort_by == "category":
        items.sort(key=lambda x: x.category or "")
    else:
        items.sort(key=lambda x: x.product_name)

    return StockDashboardResponse(
        items=items,
        total_items=len(items),
        total_value=total_value,
        low_stock_count=low_count,
        out_of_stock_count=out_count,
    )


@inventory_router.get("/{product_id}/movements", response_model=list[InventoryTxnResponse])
def get_stock_movements(product_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get stock movement history for a product."""
    inv = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Product inventory not found")

    txns = db.query(InventoryTxn).filter(
        InventoryTxn.inventory_id == inv.id
    ).order_by(InventoryTxn.created_at.desc()).limit(100).all()

    return [InventoryTxnResponse.model_validate(t) for t in txns]


@inventory_router.post("/adjust")
def adjust_inventory(data: StockAdjustRequest, db: Session = Depends(get_db)):
    """Physical stock count adjustment."""
    try:
        txn = adjust_stock(db, data.product_id, data.actual_qty, data.reason)
        db.commit()
        return {"message": "Stock adjusted", "adjustment": float(txn.qty_change)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===========================================================================
# DASHBOARD
# ===========================================================================
dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@dashboard_router.get("", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    """Home dashboard — today's summary, alerts, recent activity."""
    today = date.today()

    # Today's sales
    today_sales = db.query(func.coalesce(func.sum(Bill.total_amount), 0)).filter(
        Bill.business_id == BUSINESS_ID,
        Bill.bill_date == today,
    ).scalar()

    # Today's purchases
    today_purchases = db.query(func.coalesce(func.sum(Purchase.total_amount), 0)).filter(
        Purchase.business_id == BUSINESS_ID,
        Purchase.invoice_date == today,
    ).scalar()

    # Today's expenses
    today_expenses = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.business_id == BUSINESS_ID,
        Expense.expense_date == today,
    ).scalar()

    # Low stock count
    low_stock = db.query(func.count()).select_from(Product).outerjoin(
        Inventory, Inventory.product_id == Product.id
    ).filter(
        Product.business_id == BUSINESS_ID,
        Product.is_active == True,
        Product.low_stock_threshold > 0,
        (Inventory.qty_primary <= Product.low_stock_threshold) | (Inventory.qty_primary == None),
    ).scalar()

    # Overdue customers (outstanding > 0)
    overdue = db.query(func.count()).filter(
        Customer.business_id == BUSINESS_ID,
        Customer.outstanding > 0,
    ).scalar()

    return DashboardResponse(
        today_sales=Decimal(str(today_sales)),
        today_purchases=Decimal(str(today_purchases)),
        today_expenses=Decimal(str(today_expenses)),
        low_stock_count=low_stock or 0,
        overdue_count=overdue or 0,
    )
