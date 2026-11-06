"""
KTS — Inventory Service
All stock-affecting operations go through here.
Every mutation is wrapped in a DB transaction and creates an audit trail (inventory_txn).
"""
from decimal import Decimal
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.models import Inventory, InventoryTxn, Product


def get_stock(db: Session, product_id: UUID) -> dict:
    """
    Get current stock for a product in both units.
    Returns: {qty_primary, qty_secondary, unit_primary, unit_secondary, value_at_cost}
    """
    inv = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    product = db.query(Product).filter(Product.id == product_id).first()

    if not inv or not product:
        return {"qty_primary": Decimal("0"), "qty_secondary": Decimal("0")}

    qty_secondary = inv.qty_primary * product.conversion_factor

    return {
        "qty_primary": inv.qty_primary,
        "qty_secondary": qty_secondary,
        "unit_primary": product.primary_unit,
        "unit_secondary": product.secondary_unit,
        "value_at_cost": inv.qty_primary * product.purchase_price,
    }


def stock_in(
    db: Session,
    product_id: UUID,
    quantity: Decimal,
    unit: str,
    reference_type: str,
    reference_id: UUID,
    user_id: UUID | None = None,
    note: str | None = None,
) -> InventoryTxn:
    """
    Add stock (from a purchase, return, or adjustment).
    Quantity should be in PRIMARY unit.
    """
    inv = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    if not inv:
        raise ValueError(f"No inventory record for product {product_id}")

    inv.qty_primary += quantity

    txn = InventoryTxn(
        id=uuid4(),
        inventory_id=inv.id,
        txn_type="purchase_in" if reference_type == "purchase" else "return_in",
        qty_change=quantity,
        unit=unit,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
        created_by=user_id,
    )
    db.add(txn)
    return txn


def stock_out(
    db: Session,
    product_id: UUID,
    quantity: Decimal,
    unit: str,
    reference_type: str,
    reference_id: UUID,
    user_id: UUID | None = None,
    note: str | None = None,
    allow_negative: bool = False,
) -> InventoryTxn:
    """
    Remove stock (from a sale or transfer).
    Quantity should be in PRIMARY unit (positive value — will be stored as negative).
    Raises ValueError if stock would go negative (unless allow_negative=True).
    """
    inv = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    if not inv:
        raise ValueError(f"No inventory record for product {product_id}")

    if not allow_negative and inv.qty_primary < quantity:
        raise ValueError(
            f"Insufficient stock for product {product_id}: "
            f"available={inv.qty_primary}, requested={quantity}"
        )

    inv.qty_primary -= quantity

    txn = InventoryTxn(
        id=uuid4(),
        inventory_id=inv.id,
        txn_type="sale_out",
        qty_change=-quantity,  # negative for outflow
        unit=unit,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
        created_by=user_id,
    )
    db.add(txn)
    return txn


def record_wastage(
    db: Session,
    product_id: UUID,
    quantity: Decimal,
    unit: str,
    reference_id: UUID | None = None,
    user_id: UUID | None = None,
    note: str | None = None,
) -> InventoryTxn:
    """Record wastage/damage — deducts from stock, logs as loss."""
    inv = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    if not inv:
        raise ValueError(f"No inventory record for product {product_id}")

    inv.qty_primary -= quantity

    txn = InventoryTxn(
        id=uuid4(),
        inventory_id=inv.id,
        txn_type="wastage",
        qty_change=-quantity,
        unit=unit,
        reference_type="wastage",
        reference_id=reference_id,
        note=note or "Damaged/short on arrival",
        created_by=user_id,
    )
    db.add(txn)
    return txn


def adjust_stock(
    db: Session,
    product_id: UUID,
    actual_qty: Decimal,
    reason: str,
    user_id: UUID | None = None,
) -> InventoryTxn:
    """
    Physical count adjustment — sets stock to actual_qty, logs the difference.
    reason: 'damage', 'theft', 'measurement_error', 'personal_use'
    """
    inv = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    if not inv:
        raise ValueError(f"No inventory record for product {product_id}")

    product = db.query(Product).filter(Product.id == product_id).first()
    difference = actual_qty - inv.qty_primary
    inv.qty_primary = actual_qty

    txn = InventoryTxn(
        id=uuid4(),
        inventory_id=inv.id,
        txn_type="adjustment",
        qty_change=difference,
        unit=product.primary_unit if product else "unit",
        reference_type="stock_count",
        note=f"Physical count adjustment: {reason}",
        created_by=user_id,
    )
    db.add(txn)
    return txn


def convert_to_primary_unit(
    db: Session,
    product_id: UUID,
    qty_in_secondary: Decimal,
) -> Decimal:
    """
    Convert a quantity from secondary unit to primary unit.
    e.g., 12.5 Kg → 0.25 Bags (if conversion_factor = 50)
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product or not product.conversion_factor:
        return qty_in_secondary

    return qty_in_secondary / product.conversion_factor
