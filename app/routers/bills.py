"""
KTS — Bill Router
Bill creation is the most-used operation (<30s for 5 items).
Every bill: auto-GST, locked stock deduction at moving-average cost, ledger update.
Bills are never deleted — they are cancelled, which reverses stock and ledger.
"""
import urllib.parse
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ADMIN, FIELD, OPS, RequestContext, allow
from app.models import Bill, BillItem, Business, Customer, Inventory, InventoryTxn, LedgerEntry, Product
from app.schemas.transactions import (
    BillCancelRequest, BillCreate, BillItemResponse, BillListResponse, BillResponse,
)
from app.services.gst_engine import calculate_line_gst, round_to_rupee
from app.services.inventory_service import lock_inventories, stock_in, stock_out, to_primary_qty
from app.services.numbering import next_document_number
from app.utils.scoping import get_owned

router = APIRouter(prefix="/api/v1/bills", tags=["Bills"])

COST_Q = Decimal("0.0001")


def _bill_to_response(bill: Bill, db: Session, warnings: list[str] | None = None) -> BillResponse:
    customer = db.get(Customer, bill.customer_id)
    product_ids = {i.product_id for i in bill.items}
    names = {
        p.id: p.name
        for p in db.query(Product).filter(Product.id.in_(product_ids), Product.business_id == bill.business_id)
    } if product_ids else {}

    return BillResponse(
        id=bill.id,
        customer_id=bill.customer_id,
        customer_name=customer.name if customer else None,
        bill_number=bill.bill_number,
        bill_date=bill.bill_date,
        bill_type=bill.bill_type,
        subtotal=bill.subtotal,
        cgst_amount=bill.cgst_amount,
        sgst_amount=bill.sgst_amount,
        igst_amount=bill.igst_amount,
        round_off=bill.round_off or Decimal("0"),
        total_amount=bill.total_amount,
        status=bill.status,
        cancelled_at=bill.cancelled_at,
        cancel_reason=bill.cancel_reason,
        payment_status=bill.payment_status,
        amount_paid=bill.amount_paid,
        payment_mode=bill.payment_mode,
        items=[
            BillItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=names.get(item.product_id),
                quantity=item.quantity,
                unit=item.unit,
                rate=item.rate,
                discount_pct=item.discount_pct,
                gst_rate=item.gst_rate,
                cgst_amount=item.cgst_amount,
                sgst_amount=item.sgst_amount,
                igst_amount=item.igst_amount,
                total=item.total,
                cost_basis=item.cost_basis,
            )
            for item in bill.items
        ],
        created_at=bill.created_at,
        warnings=warnings or [],
    )


@router.post("", response_model=BillResponse, status_code=201)
def create_bill(data: BillCreate, ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    """
    Create a sale bill in one transaction:
    validate → lock stock rows → GST → FY bill number → deduct stock →
    record moving-average cost_basis → customer outstanding + ledger.
    """
    business = db.get(Business, ctx.business_id)
    if not business.state_code:
        raise HTTPException(status_code=400, detail="Complete business setup (state code) before billing")
    business_state = business.state_code

    customer = get_owned(db, Customer, data.customer_id, ctx, detail="Customer not found", for_update=True)
    customer_state = customer.state_code or business_state

    products = {
        p.id: p
        for p in db.query(Product).filter(
            Product.id.in_({i.product_id for i in data.items}),
            Product.business_id == ctx.business_id,
            Product.is_active.is_(True),
        )
    }
    for item in data.items:
        if item.product_id not in products:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

    # Lock every inventory row up front, in a stable order.
    inventories = lock_inventories(db, ctx.business_id, list(products))

    bill_id = uuid.uuid4()
    bill_date = data.bill_date or date.today()
    totals = {"subtotal": Decimal("0"), "cgst": Decimal("0"), "sgst": Decimal("0"), "igst": Decimal("0")}
    bill_items: list[BillItem] = []
    deductions: list[tuple[uuid.UUID, Decimal, str]] = []
    needed: dict[uuid.UUID, Decimal] = {}

    for item_data in data.items:
        product = products[item_data.product_id]
        inv = inventories.get(product.id)
        billing_qty = Decimal(str(item_data.quantity))
        primary_qty = to_primary_qty(product, billing_qty, item_data.unit)

        needed[product.id] = needed.get(product.id, Decimal("0")) + primary_qty
        available = inv.qty_primary if inv else Decimal("0")
        if available < needed[product.id]:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock for {product.name}: available={available} "
                    f"{product.primary_unit}, requested={needed[product.id]} {product.primary_unit}"
                ),
            )

        rate = Decimal(str(item_data.rate))
        disc = Decimal(str(item_data.discount_pct))
        line_amount = (billing_qty * rate).quantize(Decimal("0.01"))
        if disc > 0:
            line_amount -= (line_amount * disc / Decimal("100")).quantize(Decimal("0.01"))

        gst = calculate_line_gst(
            amount=line_amount, gst_rate=product.gst_rate,
            supplier_state=business_state, customer_state=customer_state,
        )

        # Cost per billed unit = moving-average cost per primary unit × primary units per billed unit
        avg_cost = inv.avg_cost if inv else Decimal("0")
        cost_basis = (avg_cost * primary_qty / billing_qty).quantize(COST_Q)

        bill_items.append(BillItem(
            id=uuid.uuid4(),
            bill_id=bill_id,
            product_id=product.id,
            quantity=billing_qty,
            unit=item_data.unit or product.secondary_unit or product.primary_unit,
            rate=rate,
            discount_pct=disc,
            gst_rate=product.gst_rate,
            cgst_amount=gst.cgst,
            sgst_amount=gst.sgst,
            igst_amount=gst.igst,
            total=gst.total,
            cost_basis=cost_basis,
        ))
        totals["subtotal"] += gst.subtotal
        totals["cgst"] += gst.cgst
        totals["sgst"] += gst.sgst
        totals["igst"] += gst.igst
        deductions.append((product.id, primary_qty, product.primary_unit))

    gross = (totals["subtotal"] + totals["cgst"] + totals["sgst"] + totals["igst"]).quantize(Decimal("0.01"))
    total_amount, round_off = round_to_rupee(gross)

    amount_paid = Decimal(str(data.amount_paid))
    if data.payment_status == "paid":
        amount_paid = total_amount
    if amount_paid > total_amount:
        raise HTTPException(status_code=400, detail="amount_paid cannot exceed the bill total")
    payment_status = "paid" if amount_paid == total_amount else ("partial" if amount_paid > 0 else "credit")

    warnings: list[str] = []
    due = total_amount - amount_paid
    if customer.credit_limit > 0 and due > 0:
        new_outstanding = customer.outstanding + due
        if new_outstanding > customer.credit_limit:
            msg = (
                f"Credit limit exceeded for {customer.name}: limit={customer.credit_limit}, "
                f"outstanding would be {new_outstanding}"
            )
            if business.credit_policy == "block":
                raise HTTPException(status_code=400, detail=msg)
            warnings.append(msg)

    bill_number = next_document_number(db, business, data.bill_type, bill_date)

    bill = Bill(
        id=bill_id,
        business_id=ctx.business_id,
        customer_id=customer.id,
        bill_number=bill_number,
        bill_date=bill_date,
        bill_type=data.bill_type,
        subtotal=totals["subtotal"],
        cgst_amount=totals["cgst"],
        sgst_amount=totals["sgst"],
        igst_amount=totals["igst"],
        round_off=round_off,
        total_amount=total_amount,
        status="active",
        payment_status=payment_status,
        amount_paid=amount_paid,
        payment_mode=data.payment_mode,
        created_by=ctx.user_id,
    )
    db.add(bill)
    db.add_all(bill_items)

    for product_id, qty, unit in deductions:
        stock_out(db, ctx.business_id, product_id, qty, unit,
                  reference_type="bill", reference_id=bill_id, user_id=ctx.user_id)

    if due > 0:
        customer.outstanding += due

    db.add(LedgerEntry(
        id=uuid.uuid4(),
        business_id=ctx.business_id,
        party_type="customer",
        party_id=customer.id,
        entry_type="sale",
        amount=total_amount,
        running_balance=customer.outstanding,
        reference_type="bill",
        reference_id=bill_id,
        description=f"Bill #{bill_number} to {customer.name}",
    ))

    db.commit()
    db.refresh(bill)
    return _bill_to_response(bill, db, warnings)


@router.get("", response_model=BillListResponse)
def list_bills(
    customer_id: uuid.UUID | None = Query(None),
    bill_type: str | None = Query(None),
    payment_status: str | None = Query(None),
    status: str | None = Query(None, pattern="^(active|cancelled)$"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: RequestContext = Depends(allow(*FIELD)),
    db: Session = Depends(get_db),
):
    query = db.query(Bill).filter(Bill.business_id == ctx.business_id)
    if customer_id:
        query = query.filter(Bill.customer_id == customer_id)
    if bill_type:
        query = query.filter(Bill.bill_type == bill_type)
    if payment_status:
        query = query.filter(Bill.payment_status == payment_status)
    if status:
        query = query.filter(Bill.status == status)
    if date_from:
        query = query.filter(Bill.bill_date >= date_from)
    if date_to:
        query = query.filter(Bill.bill_date <= date_to)

    total = query.count()
    bills = query.order_by(Bill.created_at.desc()).offset(skip).limit(limit).all()
    return BillListResponse(bills=[_bill_to_response(b, db) for b in bills], total=total)


@router.get("/{bill_id}", response_model=BillResponse)
def get_bill(bill_id: uuid.UUID, ctx: RequestContext = Depends(allow(*FIELD)), db: Session = Depends(get_db)):
    return _bill_to_response(get_owned(db, Bill, bill_id, ctx, detail="Bill not found"), db)


@router.post("/{bill_id}/cancel", response_model=BillResponse)
def cancel_bill(
    bill_id: uuid.UUID,
    data: BillCancelRequest,
    ctx: RequestContext = Depends(allow(*ADMIN)),
    db: Session = Depends(get_db),
):
    """
    Cancel a bill: the number stays used, stock goes back at the cost it left
    with, and the customer's ledger gets a reversing entry.
    """
    bill = get_owned(db, Bill, bill_id, ctx, detail="Bill not found", for_update=True)
    if bill.status == "cancelled":
        raise HTTPException(status_code=409, detail="Bill is already cancelled")

    customer = get_owned(db, Customer, bill.customer_id, ctx, detail="Customer not found", for_update=True)

    outflows = db.query(InventoryTxn).filter(
        InventoryTxn.business_id == ctx.business_id,
        InventoryTxn.reference_type == "bill",
        InventoryTxn.reference_id == bill.id,
        InventoryTxn.txn_type == "sale_out",
    ).all()
    inv_to_product = {
        i.id: i.product_id
        for i in db.query(Inventory).filter(Inventory.id.in_({t.inventory_id for t in outflows}))
    } if outflows else {}
    lock_inventories(db, ctx.business_id, list(inv_to_product.values()))
    for txn in outflows:
        stock_in(
            db, ctx.business_id, inv_to_product[txn.inventory_id], -txn.qty_change, txn.unit,
            txn_type="sale_reversal", unit_cost=txn.unit_cost,
            reference_type="bill_cancel", reference_id=bill.id, user_id=ctx.user_id,
            note=f"Cancelled bill {bill.bill_number}",
        )

    due = bill.total_amount - bill.amount_paid
    if due > 0:
        customer.outstanding -= due
    description = f"Bill #{bill.bill_number} cancelled: {data.reason}"
    if bill.amount_paid > 0:
        description += f" (₹{bill.amount_paid} was collected on this bill — refund or keep as advance)"
    db.add(LedgerEntry(
        id=uuid.uuid4(),
        business_id=ctx.business_id,
        party_type="customer",
        party_id=customer.id,
        entry_type="sale_cancel",
        amount=bill.total_amount,
        running_balance=customer.outstanding,
        reference_type="bill",
        reference_id=bill.id,
        description=description,
    ))

    bill.status = "cancelled"
    bill.cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    bill.cancel_reason = data.reason
    bill.cancelled_by = ctx.user_id
    db.commit()
    db.refresh(bill)
    return _bill_to_response(bill, db)


# ---------------------------------------------------------------------------
# PDF DOWNLOAD
# ---------------------------------------------------------------------------

@router.get("/{bill_id}/pdf")
def download_bill_pdf(
    bill_id: uuid.UUID,
    format: str = Query("a4", pattern="^(a4|thermal)$"),
    ctx: RequestContext = Depends(allow(*FIELD)),
    db: Session = Depends(get_db),
):
    """Download the bill as a PDF (A4 or 80mm thermal)."""
    from app.services.bill_pdf import generate_bill_pdf

    bill_resp = _bill_to_response(get_owned(db, Bill, bill_id, ctx, detail="Bill not found"), db)
    bill_data = {
        "bill_number": bill_resp.bill_number,
        "bill_date": str(bill_resp.bill_date),
        "bill_type": bill_resp.bill_type,
        "status": bill_resp.status,
        "customer_name": bill_resp.customer_name or "Walk-in Customer",
        "items": [
            {
                "product_name": item.product_name or "Item",
                "quantity": float(item.quantity),
                "unit": item.unit,
                "rate": float(item.rate),
                "gst_rate": float(item.gst_rate),
                "total": float(item.total),
            }
            for item in bill_resp.items
        ],
        "subtotal": float(bill_resp.subtotal),
        "cgst_amount": float(bill_resp.cgst_amount),
        "sgst_amount": float(bill_resp.sgst_amount),
        "igst_amount": float(bill_resp.igst_amount),
        "round_off": float(bill_resp.round_off),
        "total_amount": float(bill_resp.total_amount),
        "payment_status": bill_resp.payment_status,
        "amount_paid": float(bill_resp.amount_paid),
    }
    business = db.get(Business, ctx.business_id)
    business_data = {
        "name": business.name,
        "address": business.address or "",
        "gstin": business.gstin or "",
        "phone": business.phone or "",
    }

    pdf_bytes = generate_bill_pdf(bill_data, business_data, format=format)
    filename = bill_resp.bill_number.replace("/", "-") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# WHATSAPP SHARE
# ---------------------------------------------------------------------------

@router.get("/{bill_id}/share/whatsapp")
def whatsapp_share_link(
    bill_id: uuid.UUID,
    ctx: RequestContext = Depends(allow(*FIELD)),
    db: Session = Depends(get_db),
):
    """Pre-formatted bill summary and a wa.me deep link. The PDF is attached client-side."""
    bill = get_owned(db, Bill, bill_id, ctx, detail="Bill not found")
    bill_resp = _bill_to_response(bill, db)
    customer = db.get(Customer, bill.customer_id)

    lines = [
        f"*Invoice #{bill_resp.bill_number}*",
        f"Date: {bill_resp.bill_date}",
        f"{bill_resp.customer_name or 'Customer'}",
        "",
        "─────────────────",
    ]
    if bill_resp.status == "cancelled":
        lines.insert(0, "*CANCELLED*")
    for item in bill_resp.items:
        lines.append(f"• {item.product_name or 'Item'} × {item.quantity} {item.unit} @ ₹{item.rate}")
        lines.append(f"  = ₹{item.total}")
    lines.extend(["─────────────────", f"Subtotal: ₹{bill_resp.subtotal}"])

    gst_total = bill_resp.cgst_amount + bill_resp.sgst_amount + bill_resp.igst_amount
    if gst_total > 0:
        lines.append(f"GST: ₹{gst_total:.2f}")
    if bill_resp.round_off:
        lines.append(f"Round off: ₹{bill_resp.round_off}")
    lines.extend([f"*Total: ₹{bill_resp.total_amount}*", ""])

    if bill_resp.payment_status == "paid":
        lines.append("PAID IN FULL")
    elif bill_resp.payment_status == "partial":
        lines.append(f"Paid: ₹{bill_resp.amount_paid} | Due: ₹{bill_resp.total_amount - bill_resp.amount_paid:.2f}")
    else:
        lines.append(f"Due: ₹{bill_resp.total_amount}")
    lines.append("\n_Generated by Karma Tattva Samiksha_")

    message = "\n".join(lines)
    phone = customer.phone.lstrip("+") if customer and customer.phone else ""
    encoded = urllib.parse.quote(message)
    return {
        "wa_link": f"https://wa.me/{phone}?text={encoded}" if phone else f"https://wa.me/?text={encoded}",
        "message": message,
        "customer_phone": customer.phone if customer else None,
        "bill_number": bill_resp.bill_number,
    }
