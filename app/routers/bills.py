"""
KTS — Bill Router
Bill creation is the most-used operation (<30s for 5 items).
Every bill: auto-GST, auto stock deduction, auto ledger update.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import date
import uuid

from app.database import get_db
from app.models import (
    Bill, BillItem, Product, Customer, Business,
    Inventory, LedgerEntry,
)
from app.schemas.transactions import (
    BillCreate, BillResponse, BillItemResponse, BillListResponse,
)
from app.services.gst_engine import calculate_line_gst
from app.services.inventory_service import stock_out

router = APIRouter(prefix="/api/v1/bills", tags=["Bills"])

BUSINESS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _next_bill_number(db: Session) -> str:
    """Generate next bill number: PREFIX-YYYY-NNNN"""
    business = db.query(Business).filter(Business.id == BUSINESS_ID).first()
    if not business:
        prefix = "INV"
        counter = 1
    else:
        prefix = business.bill_prefix or "INV"
        business.bill_counter += 1
        counter = business.bill_counter

    year = date.today().year
    return f"{prefix}-{year}-{counter:04d}"


def _bill_to_response(bill: Bill, db: Session) -> BillResponse:
    customer = db.query(Customer).filter(Customer.id == bill.customer_id).first()

    item_responses = []
    for item in bill.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        item_responses.append(BillItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=product.name if product else None,
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
        ))

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
        total_amount=bill.total_amount,
        payment_status=bill.payment_status,
        amount_paid=bill.amount_paid,
        payment_mode=bill.payment_mode,
        items=item_responses,
        created_at=bill.created_at,
    )


@router.post("", response_model=BillResponse, status_code=201)
def create_bill(data: BillCreate, db: Session = Depends(get_db)):
    """
    Create a sale bill (TRANSACTIONAL).

    This is the most-used operation. On save:
    1. Validate customer + all products
    2. Check stock availability for each item
    3. Auto-calculate GST (CGST+SGST or IGST based on states)
    4. Generate bill number
    5. Deduct stock for each item
    6. Update customer ledger + outstanding
    7. Record cost_basis on each bill_item for Phase 2 analytics
    """
    # Get business for state code
    business = db.query(Business).filter(Business.id == BUSINESS_ID).first()
    business_state = business.state_code or "27" if business else "27"

    # Validate customer
    customer = db.query(Customer).filter(
        Customer.id == data.customer_id, Customer.business_id == BUSINESS_ID
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer_state = customer.state_code or business_state

    # Credit limit check
    if customer.credit_limit > 0 and data.payment_status != "paid":
        if customer.outstanding + Decimal("1") > customer.credit_limit:  # rough check, refined below
            pass  # Warning only — don't block (configurable in future)

    bill_id = uuid.uuid4()
    bill_number = _next_bill_number(db)
    bill_date = data.bill_date or date.today()

    total_subtotal = Decimal("0")
    total_cgst = Decimal("0")
    total_sgst = Decimal("0")
    total_igst = Decimal("0")

    bill_items = []
    stock_deductions = []

    for item_data in data.items:
        product = db.query(Product).filter(
            Product.id == item_data.product_id, Product.business_id == BUSINESS_ID
        ).first()
        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {item_data.product_id} not found"
            )

        # Check stock availability
        inv = db.query(Inventory).filter(Inventory.product_id == product.id).first()
        available = inv.qty_primary if inv else Decimal("0")

        # Convert billing qty to primary unit if needed
        billing_qty = Decimal(str(item_data.quantity))
        if item_data.unit != product.primary_unit and product.conversion_factor:
            primary_qty = billing_qty / product.conversion_factor
        else:
            primary_qty = billing_qty

        if available < primary_qty:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {product.name}: available={available} {product.primary_unit}, requested={primary_qty} {product.primary_unit}"
            )

        # Line amount
        rate = Decimal(str(item_data.rate))
        disc = Decimal(str(item_data.discount_pct))
        line_amount = (billing_qty * rate).quantize(Decimal("0.01"))
        if disc > 0:
            discount = (line_amount * disc / Decimal("100")).quantize(Decimal("0.01"))
            line_amount -= discount

        # GST calculation
        gst = calculate_line_gst(
            amount=line_amount,
            gst_rate=product.gst_rate,
            supplier_state=business_state,
            customer_state=customer_state,
        )

        bill_item = BillItem(
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
            cost_basis=product.purchase_price,  # captured for Phase 2 margin analytics
        )
        bill_items.append(bill_item)

        total_subtotal += gst.subtotal
        total_cgst += gst.cgst
        total_sgst += gst.sgst
        total_igst += gst.igst

        stock_deductions.append((product.id, primary_qty, product.primary_unit))

    total_amount = (total_subtotal + total_cgst + total_sgst + total_igst).quantize(Decimal("0.01"))

    # Credit limit check (now with actual total)
    if customer.credit_limit > 0 and data.payment_status != "paid":
        new_outstanding = customer.outstanding + total_amount - data.amount_paid
        if new_outstanding > customer.credit_limit:
            raise HTTPException(
                status_code=400,
                detail=f"Credit limit exceeded for {customer.name}: limit={customer.credit_limit}, would be={new_outstanding}"
            )

    # Create bill
    bill = Bill(
        id=bill_id,
        business_id=BUSINESS_ID,
        customer_id=data.customer_id,
        bill_number=bill_number,
        bill_date=bill_date,
        bill_type=data.bill_type,
        subtotal=total_subtotal,
        cgst_amount=total_cgst,
        sgst_amount=total_sgst,
        igst_amount=total_igst,
        total_amount=total_amount,
        payment_status=data.payment_status,
        amount_paid=data.amount_paid,
        payment_mode=data.payment_mode,
    )
    db.add(bill)

    for item in bill_items:
        db.add(item)

    # Deduct stock
    for product_id, qty, unit in stock_deductions:
        stock_out(db, product_id, qty, unit, "bill", bill_id)

    # Update customer outstanding
    outstanding_increase = total_amount - data.amount_paid
    if outstanding_increase > 0:
        customer.outstanding += outstanding_increase

    # Create ledger entry
    ledger = LedgerEntry(
        id=uuid.uuid4(),
        business_id=BUSINESS_ID,
        party_type="customer",
        party_id=data.customer_id,
        entry_type="sale",
        amount=total_amount,
        running_balance=customer.outstanding,
        reference_type="bill",
        reference_id=bill_id,
        description=f"Bill #{bill_number} to {customer.name}",
    )
    db.add(ledger)

    db.commit()
    db.refresh(bill)

    return _bill_to_response(bill, db)


@router.get("", response_model=BillListResponse)
def list_bills(
    customer_id: uuid.UUID | None = Query(None),
    bill_type: str | None = Query(None),
    payment_status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List bills with filters and pagination."""
    query = db.query(Bill).filter(Bill.business_id == BUSINESS_ID)

    if customer_id:
        query = query.filter(Bill.customer_id == customer_id)
    if bill_type:
        query = query.filter(Bill.bill_type == bill_type)
    if payment_status:
        query = query.filter(Bill.payment_status == payment_status)
    if date_from:
        query = query.filter(Bill.bill_date >= date_from)
    if date_to:
        query = query.filter(Bill.bill_date <= date_to)

    total = query.count()
    bills = query.order_by(Bill.created_at.desc()).offset(skip).limit(limit).all()

    return BillListResponse(
        bills=[_bill_to_response(b, db) for b in bills],
        total=total,
    )


@router.get("/{bill_id}", response_model=BillResponse)
def get_bill(bill_id: uuid.UUID, db: Session = Depends(get_db)):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return _bill_to_response(bill, db)


# ---------------------------------------------------------------------------
# PDF DOWNLOAD — Generate printable invoice
# ---------------------------------------------------------------------------

@router.get("/{bill_id}/pdf", tags=["Bills"])
def download_bill_pdf(
    bill_id: uuid.UUID,
    format: str = Query("a4", regex="^(a4|thermal)$"),
    db: Session = Depends(get_db),
):
    """
    Download bill as a PDF (A4 or thermal 80mm format).

    Query params:
    - format: "a4" (default) or "thermal" for receipt printers

    Returns:
    - application/pdf binary file
    """
    from app.services.bill_pdf import generate_bill_pdf

    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    bill_resp = _bill_to_response(bill, db)

    # Build bill_data dict for the PDF generator
    bill_data = {
        "bill_number": bill_resp.bill_number,
        "bill_date": str(bill_resp.bill_date),
        "bill_type": bill_resp.bill_type,
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
        "total_amount": float(bill_resp.total_amount),
        "payment_status": bill_resp.payment_status,
        "amount_paid": float(bill_resp.amount_paid),
    }

    # Get business info for header
    business = db.query(Business).filter(Business.id == BUSINESS_ID).first()
    business_data = {
        "name": business.name if business else "KTS Business",
        "address": business.address if business else "",
        "gstin": business.gstin if business else "",
        "phone": business.phone if business else "",
    }

    pdf_bytes = generate_bill_pdf(bill_data, business_data, format=format)

    filename = f"{bill_resp.bill_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# WHATSAPP SHARE — Generate share link with bill summary
# ---------------------------------------------------------------------------

@router.get("/{bill_id}/share/whatsapp", tags=["Bills"])
def whatsapp_share_link(
    bill_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Generate WhatsApp share data for a bill.

    Returns:
    - wa_link: wa.me deep link for sharing
    - message: Pre-formatted bill summary message

    The mobile app opens this link to share via WhatsApp.
    PDF attachment is handled client-side (download PDF → share via intent).
    """
    import urllib.parse

    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    bill_resp = _bill_to_response(bill, db)
    customer = db.query(Customer).filter(Customer.id == bill.customer_id).first()

    # Build WhatsApp message
    lines = [
        f"📋 *Invoice #{bill_resp.bill_number}*",
        f"📅 Date: {bill_resp.bill_date}",
        f"👤 {bill_resp.customer_name or 'Customer'}",
        "",
        "─────────────────",
    ]

    for item in bill_resp.items:
        name = item.product_name or "Item"
        lines.append(f"• {name} × {item.quantity} {item.unit} @ ₹{item.rate}")
        lines.append(f"  = ₹{item.total}")

    lines.extend([
        "─────────────────",
        f"Subtotal: ₹{bill_resp.subtotal}",
    ])

    gst_total = float(bill_resp.cgst_amount) + float(bill_resp.sgst_amount) + float(bill_resp.igst_amount)
    if gst_total > 0:
        lines.append(f"GST: ₹{gst_total:.2f}")

    lines.extend([
        f"*Total: ₹{bill_resp.total_amount}*",
        "",
    ])

    if bill_resp.payment_status == "paid":
        lines.append("✅ PAID IN FULL")
    elif bill_resp.payment_status == "partial":
        due = float(bill_resp.total_amount) - float(bill_resp.amount_paid)
        lines.append(f"💰 Paid: ₹{bill_resp.amount_paid} | Due: ₹{due:.2f}")
    else:
        lines.append(f"🔴 Due: ₹{bill_resp.total_amount}")

    lines.append("\n_Generated by Karma Tattva Samiksha_")

    message = "\n".join(lines)

    # Build wa.me link
    phone = customer.phone.lstrip("+") if customer and customer.phone else ""
    encoded_msg = urllib.parse.quote(message)
    wa_link = f"https://wa.me/{phone}?text={encoded_msg}" if phone else f"https://wa.me/?text={encoded_msg}"

    return {
        "wa_link": wa_link,
        "message": message,
        "customer_phone": customer.phone if customer else None,
        "bill_number": bill_resp.bill_number,
    }

