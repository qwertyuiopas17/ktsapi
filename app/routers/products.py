"""
KTS — Product Router
Full CRUD for products + HSN lookup + stock info join.
Products are the master data that feeds everything else.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal
import uuid

from app.database import get_db
from app.deps import ADMIN, ALL_ROLES, OPS, RequestContext, allow
from app.models import Inventory, Product
from app.schemas.entities import (
    HsnLookupResponse, ProductCreate, ProductListResponse, ProductResponse, ProductUpdate,
)
from app.services.gst_engine import lookup_gst_rate, lookup_hsn
from app.utils.scoping import get_owned

router = APIRouter(prefix="/api/v1/products", tags=["Products"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _product_to_response(product: Product, db: Session) -> ProductResponse:
    """Convert model to response, joining inventory data."""
    inv = db.query(Inventory).filter(
        Inventory.product_id == product.id, Inventory.business_id == product.business_id
    ).first()
    current_stock = inv.qty_primary if inv else Decimal("0")
    avg_cost = inv.avg_cost if inv else Decimal("0")

    return ProductResponse(
        id=product.id,
        name=product.name,
        shortcode=product.shortcode,
        hsn_code=product.hsn_code,
        gst_rate=product.gst_rate,
        category=product.category,
        primary_unit=product.primary_unit,
        secondary_unit=product.secondary_unit,
        conversion_factor=product.conversion_factor,
        purchase_price=product.purchase_price,
        sell_price_retail=product.sell_price_retail,
        sell_price_wholesale=product.sell_price_wholesale,
        sell_price_special=product.sell_price_special,
        low_stock_threshold=product.low_stock_threshold,
        is_loose_stock=product.is_loose_stock,
        is_active=product.is_active,
        created_at=product.created_at,
        current_stock=current_stock,
        avg_cost=avg_cost,
        stock_value=(current_stock * avg_cost).quantize(Decimal("0.01")),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=ProductResponse, status_code=201)
def create_product(data: ProductCreate, ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    """Create a new product and initialize its inventory record."""
    business_id = ctx.business_id

    # Auto-fill GST rate from HSN if provided
    if data.hsn_code and data.gst_rate == 0:
        looked_up = lookup_gst_rate(data.hsn_code)
        if looked_up is not None:
            data.gst_rate = looked_up

    product = Product(
        id=uuid.uuid4(),
        business_id=business_id,
        name=data.name,
        shortcode=data.shortcode,
        hsn_code=data.hsn_code,
        gst_rate=data.gst_rate,
        category=data.category,
        primary_unit=data.primary_unit,
        secondary_unit=data.secondary_unit,
        conversion_factor=data.conversion_factor,
        purchase_price=data.purchase_price,
        sell_price_retail=data.sell_price_retail,
        sell_price_wholesale=data.sell_price_wholesale,
        sell_price_special=data.sell_price_special,
        low_stock_threshold=data.low_stock_threshold,
        is_loose_stock=data.is_loose_stock,
    )
    db.add(product)

    # Initialize inventory record at 0
    inventory = Inventory(
        id=uuid.uuid4(),
        business_id=business_id,
        product_id=product.id,
        qty_primary=Decimal("0"),
    )
    db.add(inventory)

    db.commit()
    db.refresh(product)

    return _product_to_response(product, db)


@router.get("", response_model=ProductListResponse)
def list_products(
    search: str | None = Query(None, description="Search by name or shortcode"),
    category: str | None = Query(None),
    is_active: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: RequestContext = Depends(allow(*ALL_ROLES)),
    db: Session = Depends(get_db),
):
    """List products with search, filter, and pagination."""
    business_id = ctx.business_id

    query = db.query(Product).filter(
        Product.business_id == business_id,
        Product.is_active == is_active,
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Product.name.ilike(search_term)) | (Product.shortcode.ilike(search_term))
        )

    if category:
        query = query.filter(Product.category == category)

    total = query.count()
    products = query.order_by(Product.name).offset(skip).limit(limit).all()

    return ProductListResponse(
        products=[_product_to_response(p, db) for p in products],
        total=total,
    )


@router.get("/hsn-lookup", response_model=HsnLookupResponse)
def hsn_lookup(
    hsn_code: str = Query(..., min_length=4, max_length=8),
    on_date: date | None = Query(None, description="Rate in force on this date (default today)"),
    ctx: RequestContext = Depends(allow(*ALL_ROLES)),
):
    """Look up the GST rate for an HSN code on a date."""
    found = lookup_hsn(hsn_code, on_date)
    return HsnLookupResponse(
        hsn_code=hsn_code,
        gst_rate=found.rate if found else None,
        cess_rate=found.cess_rate if found else None,
        description=found.description if found else None,
        note=found.note if found else None,
        requires_ca_review=found.requires_ca_review if found else False,
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: uuid.UUID, ctx: RequestContext = Depends(allow(*ALL_ROLES)), db: Session = Depends(get_db)):
    """Get a single product by ID."""
    product = get_owned(db, Product, product_id, ctx, detail="Product not found")
    return _product_to_response(product, db)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: uuid.UUID,
    data: ProductUpdate,
    ctx: RequestContext = Depends(allow(*OPS)),
    db: Session = Depends(get_db),
):
    """Update a product (partial update)."""
    product = get_owned(db, Product, product_id, ctx, detail="Product not found")

    update_data = data.model_dump(exclude_unset=True)

    # Re-lookup GST if HSN changed
    if "hsn_code" in update_data and update_data["hsn_code"]:
        looked_up = lookup_gst_rate(update_data["hsn_code"])
        if looked_up is not None and "gst_rate" not in update_data:
            update_data["gst_rate"] = looked_up

    for key, value in update_data.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)

    return _product_to_response(product, db)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: uuid.UUID, ctx: RequestContext = Depends(allow(*ADMIN)), db: Session = Depends(get_db)):
    """Soft-delete a product (set is_active = False)."""
    product = get_owned(db, Product, product_id, ctx, detail="Product not found")

    product.is_active = False
    db.commit()
