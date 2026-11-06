"""
KTS — Payment, Ledger, Inventory, and Dashboard Routers
"""
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import FIELD, OPS, STOCK, STOCK_ADJUST, RequestContext, allow
from app.models import (
    Bill, Company, Customer, Expense, Inventory, InventoryTxn, LedgerEntry, Payment, Product, Purchase,
)
from app.schemas.transactions import (
    DashboardResponse, InventoryTxnResponse, LedgerEntryResponse, OutstandingResponse,
    PartyLedgerResponse, PaymentCreate, PaymentListResponse, PaymentResponse,
    StockAdjustmentBatch, StockAdjustmentBatchResponse, StockAdjustmentLineResult,
    StockAdjustRequest, StockDashboardResponse, StockItem,
)
from app.services.inventory_service import adjust_stock, lock_inventories, stock_in
from app.utils.scoping import get_owned

_PARTY_MODELS = {"customer": Customer, "company": Company}


def _party_model(party_type: str):
    model = _PARTY_MODELS.get(party_type)
    if model is None:
        raise HTTPException(status_code=400, detail="party_type must be 'customer' or 'company'")
    return model


# ===========================================================================
# PAYMENTS
# ===========================================================================
payment_router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@payment_router.post("", response_model=PaymentResponse, status_code=201)
def record_payment(data: PaymentCreate, ctx: RequestContext = Depends(allow(*FIELD)), db: Session = Depends(get_db)):
    """
    Record a payment received from a customer or made to a supplier.
    Delivery staff may only record customer collections.
    """
    if ctx.role == "delivery" and data.party_type != "customer":
        raise HTTPException(status_code=403, detail="Your role cannot perform this action")

    model = _party_model(data.party_type)
    party = get_owned(db, model, data.party_id, ctx, detail=f"{model.__name__} not found", for_update=True)
    party.outstanding -= data.amount
    if party.outstanding < 0:
        # TODO(Phase 2): keep negative balances as advances instead of clamping
        party.outstanding = Decimal("0")
    entry_type = "payment_in" if data.party_type == "customer" else "payment_out"

    payment = Payment(
        id=uuid.uuid4(),
        business_id=ctx.business_id,
        party_type=data.party_type,
        party_id=party.id,
        amount=data.amount,
        payment_mode=data.payment_mode,
        payment_date=data.payment_date or date.today(),
        reference=data.reference,
        note=data.note,
        created_by=ctx.user_id,
    )
    db.add(payment)
    db.add(LedgerEntry(
        id=uuid.uuid4(),
        business_id=ctx.business_id,
        party_type=data.party_type,
        party_id=party.id,
        entry_type=entry_type,
        amount=data.amount,
        running_balance=party.outstanding,
        reference_type="payment",
        reference_id=payment.id,
        description=f"Payment {'from' if data.party_type == 'customer' else 'to'} {party.name} ({data.payment_mode})",
    ))
    db.commit()
    db.refresh(payment)

    return PaymentResponse(
        id=payment.id, party_type=payment.party_type, party_id=payment.party_id, party_name=party.name,
        amount=payment.amount, payment_mode=payment.payment_mode, payment_date=payment.payment_date,
        reference=payment.reference, note=payment.note, created_at=payment.created_at,
    )


@payment_router.get("", response_model=PaymentListResponse)
def list_payments(
    party_type: str | None = Query(None),
    party_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: RequestContext = Depends(allow(*FIELD)),
    db: Session = Depends(get_db),
):
    query = db.query(Payment).filter(Payment.business_id == ctx.business_id)
    if ctx.role == "delivery":
        party_type = "customer"
    if party_type:
        query = query.filter(Payment.party_type == party_type)
    if party_id:
        query = query.filter(Payment.party_id == party_id)

    total = query.count()
    payments = query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()

    results = []
    for p in payments:
        party = db.query(_PARTY_MODELS[p.party_type]).filter(
            _PARTY_MODELS[p.party_type].id == p.party_id,
            _PARTY_MODELS[p.party_type].business_id == ctx.business_id,
        ).first()
        results.append(PaymentResponse(
            id=p.id, party_type=p.party_type, party_id=p.party_id,
            party_name=party.name if party else None, amount=p.amount, payment_mode=p.payment_mode,
            payment_date=p.payment_date, reference=p.reference, note=p.note, created_at=p.created_at,
        ))
    return PaymentListResponse(payments=results, total=total)


# ===========================================================================
# LEDGER
# ===========================================================================
ledger_router = APIRouter(prefix="/api/v1/ledger", tags=["Ledger"])


@ledger_router.get("/outstanding", response_model=OutstandingResponse)
def get_outstanding(ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    """Outstanding dashboard — total receivable, payable, net."""
    total_receivable = db.query(func.coalesce(func.sum(Customer.outstanding), 0)).filter(
        Customer.business_id == ctx.business_id
    ).scalar()
    total_payable = db.query(func.coalesce(func.sum(Company.outstanding), 0)).filter(
        Company.business_id == ctx.business_id
    ).scalar()
    top_customers = db.query(Customer).filter(
        Customer.business_id == ctx.business_id, Customer.outstanding > 0,
    ).order_by(Customer.outstanding.desc()).limit(5).all()

    return OutstandingResponse(
        total_receivable=Decimal(str(total_receivable)),
        total_payable=Decimal(str(total_payable)),
        net_position=Decimal(str(total_receivable)) - Decimal(str(total_payable)),
        top_overdue_customers=[
            {"name": c.name, "outstanding": float(c.outstanding), "phone": c.phone} for c in top_customers
        ],
    )


@ledger_router.get("/{party_type}/{party_id}", response_model=PartyLedgerResponse)
def get_party_ledger(
    party_type: str,
    party_id: uuid.UUID,
    ctx: RequestContext = Depends(allow(*FIELD)),
    db: Session = Depends(get_db),
):
    """Full ledger for a customer or company (the Splitwise view)."""
    if ctx.role == "delivery" and party_type != "customer":
        raise HTTPException(status_code=403, detail="Your role cannot perform this action")
    party = get_owned(db, _party_model(party_type), party_id, ctx, detail="Party not found")

    entries = db.query(LedgerEntry).filter(
        LedgerEntry.business_id == ctx.business_id,
        LedgerEntry.party_type == party_type,
        LedgerEntry.party_id == party.id,
    ).order_by(LedgerEntry.created_at.desc()).limit(100).all()

    return PartyLedgerResponse(
        party_type=party_type,
        party_id=party.id,
        party_name=party.name,
        outstanding=party.outstanding,
        entries=[LedgerEntryResponse.model_validate(e) for e in entries],
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
    ctx: RequestContext = Depends(allow(*STOCK)),
    db: Session = Depends(get_db),
):
    """Live stock levels, valued at moving-average cost."""
    query = db.query(Product, Inventory).outerjoin(
        Inventory, Inventory.product_id == Product.id
    ).filter(Product.business_id == ctx.business_id, Product.is_active.is_(True))
    if category:
        query = query.filter(Product.category == category)

    items = []
    total_value = Decimal("0")
    low_count = 0
    out_count = 0
    for product, inv in query.all():
        qty_primary = inv.qty_primary if inv else Decimal("0")
        stock_value = (qty_primary * (inv.avg_cost if inv else Decimal("0"))).quantize(Decimal("0.01"))

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
            qty_secondary=qty_primary * product.conversion_factor,
            primary_unit=product.primary_unit,
            secondary_unit=product.secondary_unit,
            stock_value=stock_value,
            low_stock_threshold=product.low_stock_threshold,
            status=status,
        ))
        total_value += stock_value

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
def get_stock_movements(product_id: uuid.UUID, ctx: RequestContext = Depends(allow(*STOCK)), db: Session = Depends(get_db)):
    """Stock movement history for a product."""
    get_owned(db, Product, product_id, ctx, detail="Product not found")
    inv = db.query(Inventory).filter(
        Inventory.product_id == product_id, Inventory.business_id == ctx.business_id
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Product inventory not found")

    txns = db.query(InventoryTxn).filter(
        InventoryTxn.inventory_id == inv.id, InventoryTxn.business_id == ctx.business_id
    ).order_by(InventoryTxn.created_at.desc()).limit(100).all()
    return [InventoryTxnResponse.model_validate(t) for t in txns]


def _apply_counts(db: Session, ctx: RequestContext, batch: StockAdjustmentBatch) -> StockAdjustmentBatchResponse:
    ids = [line.product_id for line in batch.items]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Each product may appear only once per adjustment")
    products = {
        p.id: p for p in db.query(Product).filter(Product.id.in_(ids), Product.business_id == ctx.business_id)
    }
    missing = [str(i) for i in ids if i not in products]
    if missing:
        raise HTTPException(status_code=404, detail=f"Products not found: {', '.join(missing)}")

    adjustment_id = uuid.uuid4()
    inventories = lock_inventories(db, ctx.business_id, ids)
    results = []
    for line in batch.items:
        inv = inventories.get(line.product_id)
        if inv is None:
            raise HTTPException(status_code=404, detail=f"No inventory record for product {line.product_id}")
        previous = inv.qty_primary
        if batch.reason == "opening_stock" and line.unit_cost is not None and line.actual_qty > previous:
            # Opening stock carries a cost, so it feeds the moving average
            stock_in(
                db, ctx.business_id, line.product_id, line.actual_qty - previous,
                products[line.product_id].primary_unit, txn_type="purchase_in", unit_cost=line.unit_cost,
                reference_type="opening_stock", reference_id=adjustment_id, user_id=ctx.user_id,
                note=batch.note or "Opening stock",
            )
        else:
            adjust_stock(
                db, ctx.business_id, line.product_id, line.actual_qty, batch.reason,
                user_id=ctx.user_id, note=batch.note, reference_id=adjustment_id,
            )
        results.append(StockAdjustmentLineResult(
            product_id=line.product_id,
            product_name=products[line.product_id].name,
            previous_qty=previous,
            actual_qty=line.actual_qty,
            difference=line.actual_qty - previous,
        ))
    db.commit()
    return StockAdjustmentBatchResponse(adjustment_id=adjustment_id, reason=batch.reason, items=results)


@inventory_router.post("/adjustments", response_model=StockAdjustmentBatchResponse, status_code=201)
def create_stock_adjustment(
    batch: StockAdjustmentBatch,
    ctx: RequestContext = Depends(allow(*STOCK_ADJUST)),
    db: Session = Depends(get_db),
):
    """
    Apply a physical stock count (batch). Quantities are in the primary unit.
    Use reason=opening_stock with unit_cost to load opening balances at cost.
    """
    return _apply_counts(db, ctx, batch)


@inventory_router.post("/adjust", response_model=StockAdjustmentBatchResponse, deprecated=True)
def adjust_inventory(
    data: StockAdjustRequest,
    ctx: RequestContext = Depends(allow(*STOCK_ADJUST)),
    db: Session = Depends(get_db),
):
    """Single-product count. Prefer POST /inventory/adjustments."""
    return _apply_counts(db, ctx, StockAdjustmentBatch(
        reason=data.reason, items=[{"product_id": data.product_id, "actual_qty": data.actual_qty}],
    ))


# ===========================================================================
# DASHBOARD
# ===========================================================================
dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@dashboard_router.get("", response_model=DashboardResponse)
def get_dashboard(ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    """Home dashboard — today's summary and alerts."""
    today = date.today()
    biz = ctx.business_id

    today_sales = db.query(func.coalesce(func.sum(Bill.total_amount), 0)).filter(
        Bill.business_id == biz, Bill.bill_date == today, Bill.status == "active",
    ).scalar()
    today_purchases = db.query(func.coalesce(func.sum(Purchase.total_amount), 0)).filter(
        Purchase.business_id == biz, Purchase.invoice_date == today,
    ).scalar()
    today_expenses = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.business_id == biz, Expense.expense_date == today,
    ).scalar()
    low_stock = db.query(func.count()).select_from(Product).outerjoin(
        Inventory, Inventory.product_id == Product.id
    ).filter(
        Product.business_id == biz,
        Product.is_active.is_(True),
        Product.low_stock_threshold > 0,
        (Inventory.qty_primary <= Product.low_stock_threshold) | (Inventory.qty_primary.is_(None)),
    ).scalar()
    overdue = db.query(func.count(Customer.id)).filter(
        Customer.business_id == biz, Customer.outstanding > 0,
    ).scalar()

    return DashboardResponse(
        today_sales=Decimal(str(today_sales)),
        today_purchases=Decimal(str(today_purchases)),
        today_expenses=Decimal(str(today_expenses)),
        low_stock_count=low_stock or 0,
        overdue_count=overdue or 0,
    )
