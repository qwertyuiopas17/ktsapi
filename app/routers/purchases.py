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
from app.models import Purchase, PurchaseItem, Product, Company, Inventory, InventoryTxn, LedgerEntry
from app.schemas.transactions import (
    PurchaseCreate, PurchaseResponse, PurchaseItemResponse, PurchaseListResponse,
)
from app.services.inventory_service import stock_in, record_wastage

router = APIRouter(prefix="/api/v1/purchases", tags=["Purchases"])

BUSINESS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")  # dev placeholder


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
    company = db.query(Company).filter(Company.id == purchase.company_id).first()

    item_responses = []
    for item in purchase.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
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
def create_purchase(data: PurchaseCreate, db: Session = Depends(get_db)):
    """
    Create a purchase + update inventory (TRANSACTIONAL).

    This is the core "front door" operation:
    1. Validate company and all products exist
    2. Compute line item totals (qty × rate − discount + GST)
    3. Create purchase + purchase_items
    4. For each item: stock_in (good qty) + wastage (damaged qty)
    5. Update company outstanding (if credit/partial)
    6. Create ledger entry for company
    All in a single DB transaction.
    """
    # Validate company exists
    company = db.query(Company).filter(
        Company.id == data.company_id, Company.business_id == BUSINESS_ID
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    purchase_id = uuid.uuid4()
    total_subtotal = Decimal("0")
    total_gst = Decimal("0")

    purchase_items = []
    stock_ops = []  # deferred stock operations

    for item_data in data.items:
        # Validate product
        product = db.query(Product).filter(
            Product.id == item_data.product_id, Product.business_id == BUSINESS_ID
        ).first()
        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {item_data.product_id} not found"
            )

        # Auto-fill GST from product if not provided
        gst_rate = item_data.gst_rate if item_data.gst_rate > 0 else product.gst_rate

        # Compute totals
        computed = _compute_line_item(item_data)

        purchase_item = PurchaseItem(
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
        )
        purchase_items.append(purchase_item)

        total_subtotal += computed["subtotal"]
        total_gst += computed["gst_amount"]

        # Prepare stock operations
        good_qty = item_data.quantity - item_data.damaged_qty
        if good_qty > 0:
            stock_ops.append(("in", product.id, good_qty, product.primary_unit, product))
        if item_data.damaged_qty > 0:
            stock_ops.append(("wastage", product.id, item_data.damaged_qty, product.primary_unit, product))

    total_amount = (total_subtotal + total_gst).quantize(Decimal("0.01"))

    # Create purchase record
    purchase = Purchase(
        id=purchase_id,
        business_id=BUSINESS_ID,
        company_id=data.company_id,
        invoice_number=data.invoice_number,
        invoice_date=data.invoice_date or date.today(),
        subtotal=total_subtotal,
        gst_amount=total_gst,
        total_amount=total_amount,
        payment_status=data.payment_status,
        amount_paid=data.amount_paid,
        source=data.source,
        ocr_image_url=data.ocr_image_url,
    )
    db.add(purchase)

    # Add all items
    for item in purchase_items:
        db.add(item)

    # Execute stock operations
    for op_type, product_id, qty, unit, product in stock_ops:
        if op_type == "in":
            stock_in(db, product_id, qty, unit, "purchase", purchase_id)
            # Update product's latest purchase price from its matching line item
            matching = [pi for pi in purchase_items if pi.product_id == product_id]
            if matching:
                product.purchase_price = matching[0].rate
        elif op_type == "wastage":
            record_wastage(db, product_id, qty, unit, reference_id=purchase_id)

    # Update company outstanding (if credit or partial)
    outstanding_increase = total_amount - data.amount_paid
    if outstanding_increase > 0:
        company.outstanding += outstanding_increase

    # Create ledger entry
    ledger = LedgerEntry(
        id=uuid.uuid4(),
        business_id=BUSINESS_ID,
        party_type="company",
        party_id=data.company_id,
        entry_type="purchase",
        amount=total_amount,
        running_balance=company.outstanding,
        reference_type="purchase",
        reference_id=purchase_id,
        description=f"Purchase #{data.invoice_number or 'N/A'} from {company.name}",
    )
    db.add(ledger)

    # Commit everything atomically
    db.commit()
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
    db: Session = Depends(get_db),
):
    """List purchases with filters."""
    query = db.query(Purchase).filter(Purchase.business_id == BUSINESS_ID)

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
def get_purchase(purchase_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a single purchase with all items and bill image."""
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return _purchase_to_response(purchase, db)


# ---------------------------------------------------------------------------
# OCR SCAN — The magic feature
# ---------------------------------------------------------------------------

@router.post("/scan", tags=["Purchases"])
async def scan_invoice(
    file: UploadFile = File(..., description="Invoice photo (JPG/PNG) or PDF"),
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
            Company.business_id == BUSINESS_ID,
        ).first()
        if company:
            matched_company = {"id": str(company.id), "name": company.name}

    if not matched_company and result.get("company_name"):
        company = db.query(Company).filter(
            Company.name.ilike(f"%{result['company_name']}%"),
            Company.business_id == BUSINESS_ID,
        ).first()
        if company:
            matched_company = {"id": str(company.id), "name": company.name}

    # Try to match products by name
    matched_items = []
    for item in result.get("items", []):
        product_name = item.get("product_name", "")
        product = db.query(Product).filter(
            Product.name.ilike(f"%{product_name}%"),
            Product.business_id == BUSINESS_ID,
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

