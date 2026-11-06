"""
KTS — Purchase Router
Purchase capture is the front door: every purchase auto-updates inventory.
Supports manual entry (P0) and OCR scan (P0).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import date
import uuid

from app.database import get_db
from app.deps import OPS, RequestContext, allow
from app.models import Company, LedgerEntry, Product, Purchase, PurchaseItem
from app.schemas.transactions import (
    PurchaseCreate, PurchaseItemResponse, PurchaseListResponse, PurchaseResponse,
)
from app.services.inventory_service import lock_inventories, record_wastage, stock_in, to_primary_qty
from app.utils.scoping import get_owned

router = APIRouter(prefix="/api/v1/purchases", tags=["Purchases"])


def _compute_line_item(item_data) -> dict:
    """Compute derived fields for a purchase line item."""
    qty = Decimal(str(item_data.quantity))
    rate = Decimal(str(item_data.rate))
    disc_pct = Decimal(str(item_data.discount_pct))
    disc_amt = Decimal(str(item_data.discount_amount))

    # Base amount before discount
    base = qty * rate

    # Apply discount (pct takes precedence if both given)
    if disc_pct > 0:
        discount = (base * disc_pct / Decimal("100")).quantize(Decimal("0.01"))
    else:
        discount = disc_amt

    subtotal = base - discount

    # GST
    gst_rate = Decimal(str(item_data.gst_rate))
    gst_amount = (subtotal * gst_rate / Decimal("100")).quantize(Decimal("0.01"))
    total = (subtotal + gst_amount).quantize(Decimal("0.01"))

    return {
        "subtotal": subtotal,
        "gst_amount": gst_amount,
        "total": total,
        "discount_applied": discount,
    }


def _purchase_to_response(purchase: Purchase, db: Session) -> PurchaseResponse:
    """Convert Purchase model to response, joining company name and item product names."""
    company = db.get(Company, purchase.company_id)

    item_responses = []
    for item in purchase.items:
        product = db.get(Product, item.product_id)
        item_responses.append(PurchaseItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=product.name if product else None,
            quantity=item.quantity,
            unit=item.unit,
            rate=item.rate,
            discount_pct=item.discount_pct,
            discount_amount=item.discount_amount,
            damaged_qty=item.damaged_qty,
            gst_rate=item.gst_rate,
            gst_amount=item.gst_amount,
            total=item.total,
        ))

    return PurchaseResponse(
        id=purchase.id,
        company_id=purchase.company_id,
        company_name=company.name if company else None,
        invoice_number=purchase.invoice_number,
        invoice_date=purchase.invoice_date,
        subtotal=purchase.subtotal,
        gst_amount=purchase.gst_amount,
        total_amount=purchase.total_amount,
        payment_status=purchase.payment_status,
        amount_paid=purchase.amount_paid,
        source=purchase.source,
        ocr_image_url=purchase.ocr_image_url,
        ocr_confidence=purchase.ocr_confidence,
        items=item_responses,
        created_at=purchase.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=PurchaseResponse, status_code=201)
def create_purchase(data: PurchaseCreate, ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    """
    Create a purchase and receive stock in one transaction:
    1. Validate company and products (within the caller's business)
    2. Compute line totals (qty × rate − discount + GST)
    3. Stock in the full quantity at the net landed rate (ex-GST), blending the
       moving-average cost; then write damaged quantity off as wastage so the
       loss is visible (and claimable) instead of silently inflating cost
    4. Update company outstanding + ledger
    """
    company = get_owned(db, Company, data.company_id, ctx, detail="Company not found", for_update=True)

    products = {
        p.id: p
        for p in db.query(Product).filter(
            Product.id.in_({i.product_id for i in data.items}), Product.business_id == ctx.business_id
        )
    }
    for item in data.items:
        if item.product_id not in products:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if item.damaged_qty > item.quantity:
            raise HTTPException(status_code=400, detail="damaged_qty cannot exceed quantity")

    purchase_id = uuid.uuid4()
    total_subtotal = Decimal("0")
    total_gst = Decimal("0")
    purchase_items = []
    stock_ops = []

    for item_data in data.items:
        product = products[item_data.product_id]
        gst_rate = item_data.gst_rate if item_data.gst_rate > 0 else product.gst_rate
        item_for_calc = item_data.model_copy(update={"gst_rate": gst_rate})
        computed = _compute_line_item(item_for_calc)

        purchase_items.append(PurchaseItem(
            id=uuid.uuid4(),
            purchase_id=purchase_id,
            product_id=product.id,
            quantity=item_data.quantity,
            unit=item_data.unit or product.primary_unit,
            rate=item_data.rate,
            discount_pct=item_data.discount_pct,
            discount_amount=computed["discount_applied"],
            damaged_qty=item_data.damaged_qty,
            gst_rate=gst_rate,
            gst_amount=computed["gst_amount"],
            total=computed["total"],
        ))
        total_subtotal += computed["subtotal"]
        total_gst += computed["gst_amount"]

        qty_primary = to_primary_qty(product, item_data.quantity, item_data.unit)
        damaged_primary = to_primary_qty(product, item_data.damaged_qty, item_data.unit)
        landed_rate = computed["subtotal"] / qty_primary  # ex-GST cost per primary unit
        stock_ops.append((product, qty_primary, damaged_primary, landed_rate, item_data.rate))

    total_amount = (total_subtotal + total_gst).quantize(Decimal("0.01"))
    if data.amount_paid > total_amount:
        raise HTTPException(status_code=400, detail="amount_paid cannot exceed the purchase total")

    db.add(Purchase(
        id=purchase_id,
        business_id=ctx.business_id,
        company_id=company.id,
        invoice_number=data.invoice_number,
        invoice_date=data.invoice_date or date.today(),
        subtotal=total_subtotal,
        gst_amount=total_gst,
        total_amount=total_amount,
        payment_status=data.payment_status,
        amount_paid=data.amount_paid,
        source=data.source,
        ocr_image_url=data.ocr_image_url,
        created_by=ctx.user_id,
    ))
    db.add_all(purchase_items)

    lock_inventories(db, ctx.business_id, list(products))
    for product, qty_primary, damaged_primary, landed_rate, entered_rate in stock_ops:
        stock_in(
            db, ctx.business_id, product.id, qty_primary, product.primary_unit,
            txn_type="purchase_in", unit_cost=landed_rate,
            reference_type="purchase", reference_id=purchase_id, user_id=ctx.user_id,
        )
        if damaged_primary > 0:
            record_wastage(
                db, ctx.business_id, product.id, damaged_primary, product.primary_unit,
                reference_type="purchase", reference_id=purchase_id, user_id=ctx.user_id,
            )
        # Last purchase price is kept for reference; costing uses Inventory.avg_cost
        product.purchase_price = entered_rate

    outstanding_increase = total_amount - data.amount_paid
    if outstanding_increase > 0:
        company.outstanding += outstanding_increase

    db.add(LedgerEntry(
        id=uuid.uuid4(),
        business_id=ctx.business_id,
        party_type="company",
        party_id=company.id,
        entry_type="purchase",
        amount=total_amount,
        running_balance=company.outstanding,
        reference_type="purchase",
        reference_id=purchase_id,
        description=f"Purchase #{data.invoice_number or 'N/A'} from {company.name}",
    ))

    db.commit()
    purchase = db.get(Purchase, purchase_id)
    db.refresh(purchase)
    return _purchase_to_response(purchase, db)


@router.get("", response_model=PurchaseListResponse)
def list_purchases(
    company_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None, description="ocr or manual"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: RequestContext = Depends(allow(*OPS)),
    db: Session = Depends(get_db),
):
    """List purchases with filters."""
    query = db.query(Purchase).filter(Purchase.business_id == ctx.business_id)

    if company_id:
        query = query.filter(Purchase.company_id == company_id)
    if source:
        query = query.filter(Purchase.source == source)
    if date_from:
        query = query.filter(Purchase.invoice_date >= date_from)
    if date_to:
        query = query.filter(Purchase.invoice_date <= date_to)

    total = query.count()
    purchases = query.order_by(Purchase.created_at.desc()).offset(skip).limit(limit).all()

    return PurchaseListResponse(
        purchases=[_purchase_to_response(p, db) for p in purchases],
        total=total,
    )


@router.get("/{purchase_id}", response_model=PurchaseResponse)
def get_purchase(purchase_id: uuid.UUID, ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    """Get a single purchase with all items and bill image."""
    return _purchase_to_response(get_owned(db, Purchase, purchase_id, ctx, detail="Purchase not found"), db)


# ---------------------------------------------------------------------------
# OCR SCAN — The magic feature
# ---------------------------------------------------------------------------

@router.post("/scan", tags=["Purchases"])
async def scan_invoice(
    file: UploadFile = File(..., description="Invoice photo (JPG/PNG) or PDF"),
    ctx: RequestContext = Depends(allow(*OPS)),
    db: Session = Depends(get_db),
):
    """
    OCR Invoice Scanner (P0 feature).

    Upload a photo of a purchase invoice (or PDF) and get back
    structured data ready to create a purchase.

    Flow:
    1. User snaps a photo of the supplier invoice
    2. This endpoint extracts: company, items, quantities, rates, GST
    3. Frontend shows the extracted data for review
    4. User confirms → calls POST /purchases with the data

    Supports: JPG, PNG, WebP, PDF (first page)
    """
    from app.services.ocr_service import scan_invoice as _scan

    # Validate file type
    allowed_types = {
        "image/jpeg", "image/png", "image/webp",
        "application/pdf",
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Use JPG, PNG, WebP, or PDF."
        )

    # Read file (limit 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")

    # Run OCR
    result = await _scan(contents, file.filename or "invoice.jpg")

    if "error" in result:
        return {
            "status": "error",
            "error": result["error"],
            "confidence": 0,
            "extracted_data": None,
        }

    # Try to match company by GSTIN or name
    matched_company = None
    if result.get("gstin"):
        company = db.query(Company).filter(
            Company.gstin == result["gstin"],
            Company.business_id == ctx.business_id,
        ).first()
        if company:
            matched_company = {"id": str(company.id), "name": company.name}

    if not matched_company and result.get("company_name"):
        company = db.query(Company).filter(
            Company.name.ilike(f"%{result['company_name']}%"),
            Company.business_id == ctx.business_id,
        ).first()
        if company:
            matched_company = {"id": str(company.id), "name": company.name}

    # Try to match products by name
    matched_items = []
    for item in result.get("items", []):
        product_name = item.get("product_name", "")
        product = db.query(Product).filter(
            Product.name.ilike(f"%{product_name}%"),
            Product.business_id == ctx.business_id,
        ).first()

        matched_items.append({
            "extracted_name": product_name,
            "matched_product": {
                "id": str(product.id),
                "name": product.name,
                "hsn_code": product.hsn_code,
                "gst_rate": float(product.gst_rate),
            } if product else None,
            "quantity": item.get("quantity"),
            "unit": item.get("unit"),
            "rate": item.get("rate"),
            "discount_pct": item.get("discount_pct", 0),
            "gst_rate": item.get("gst_rate"),
            "amount": item.get("amount"),
            "hsn_code": item.get("hsn_code"),
        })

    return {
        "status": "success",
        "confidence": result.get("confidence", 0),
        "matched_company": matched_company,
        "invoice_number": result.get("invoice_number"),
        "invoice_date": result.get("invoice_date"),
        "items": matched_items,
        "totals": {
            "subtotal": result.get("subtotal"),
            "cgst": result.get("cgst_amount"),
            "sgst": result.get("sgst_amount"),
            "igst": result.get("igst_amount"),
            "total": result.get("total_amount"),
        },
        "source": "ocr",
        "message": "Review the extracted data and confirm to create the purchase.",
    }

