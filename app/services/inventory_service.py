"""
KTS — Inventory Service
All stock-affecting operations go through here. Each one:
  - locks the inventory row (SELECT ... FOR UPDATE) so concurrent bills cannot oversell,
  - is scoped to the caller's business,
  - writes an InventoryTxn audit row with the cost per primary unit.

Costing is moving-average: purchase receipts (and reversals) blend into
Inventory.avg_cost; outflows are valued at the current avg_cost.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import Inventory, InventoryTxn, Product

COST_Q = Decimal("0.0001")
_COST_BEARING_IN = {"purchase_in", "return_in", "sale_reversal"}


class InventoryError(ValueError):
    status_code = 400


class InventoryNotFound(InventoryError):
    status_code = 404


class InsufficientStock(InventoryError):
    status_code = 400


def to_primary_qty(product: Product, qty: Decimal, unit: str | None) -> Decimal:
    """Convert a quantity entered in `unit` into the product's primary (stocking) unit."""
    qty = Decimal(str(qty))
    if unit and unit != product.primary_unit and product.conversion_factor:
        return qty / Decimal(str(product.conversion_factor))
    return qty


def lock_inventories(db: Session, business_id: UUID, product_ids: list[UUID]) -> dict[UUID, Inventory]:
    """
    Lock several inventory rows at once, in a stable order, to avoid deadlocks
    between two bills that contain the same products in a different order.
    """
    db.flush()  # populate_existing() below must not discard unflushed changes
    rows = (
        db.query(Inventory)
        .filter(Inventory.business_id == business_id, Inventory.product_id.in_(set(product_ids)))
        .order_by(Inventory.product_id)
        .with_for_update()
        .populate_existing()
        .all()
    )
    return {r.product_id: r for r in rows}


def _locked(db: Session, business_id: UUID, product_id: UUID) -> Inventory:
    db.flush()  # populate_existing() below must not discard unflushed changes
    inv = (
        db.query(Inventory)
        .filter(Inventory.business_id == business_id, Inventory.product_id == product_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if inv is None:
        raise InventoryNotFound(f"No inventory record for product {product_id}")
    return inv


def get_stock(db: Session, business_id: UUID, product_id: UUID) -> dict:
    inv = db.query(Inventory).filter(
        Inventory.business_id == business_id, Inventory.product_id == product_id
    ).first()
    product = db.query(Product).filter(
        Product.business_id == business_id, Product.id == product_id
    ).first()
    if not inv or not product:
        return {"qty_primary": Decimal("0"), "qty_secondary": Decimal("0")}
    return {
        "qty_primary": inv.qty_primary,
        "qty_secondary": inv.qty_primary * product.conversion_factor,
        "unit_primary": product.primary_unit,
        "unit_secondary": product.secondary_unit,
        "avg_cost": inv.avg_cost,
        "value_at_cost": inv.qty_primary * inv.avg_cost,
    }


def stock_in(
    db: Session,
    business_id: UUID,
    product_id: UUID,
    quantity: Decimal,
    unit: str,
    *,
    txn_type: str,
    reference_type: str,
    reference_id: UUID | None,
    unit_cost: Decimal | None = None,
    user_id: UUID | None = None,
    note: str | None = None,
) -> InventoryTxn:
    """
    Add stock. `quantity` is in the PRIMARY unit; `unit_cost` is ex-GST landed
    cost per primary unit and is blended into the moving average.
    """
    if txn_type not in {"purchase_in", "return_in", "sale_reversal", "adjustment", "transfer"}:
        raise InventoryError(f"Invalid inbound txn_type {txn_type}")
    quantity = Decimal(str(quantity))
    inv = _locked(db, business_id, product_id)

    if unit_cost is not None and txn_type in _COST_BEARING_IN and quantity > 0:
        unit_cost = Decimal(str(unit_cost))
        on_hand = inv.qty_primary or Decimal("0")
        if on_hand <= 0:
            inv.avg_cost = unit_cost.quantize(COST_Q)
        else:
            inv.avg_cost = (
                (on_hand * (inv.avg_cost or 0) + quantity * unit_cost) / (on_hand + quantity)
            ).quantize(COST_Q)

    inv.qty_primary = (inv.qty_primary or Decimal("0")) + quantity
    txn = InventoryTxn(
        id=uuid4(),
        business_id=business_id,
        inventory_id=inv.id,
        txn_type=txn_type,
        qty_change=quantity,
        unit_cost=unit_cost if unit_cost is not None else inv.avg_cost,
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
    business_id: UUID,
    product_id: UUID,
    quantity: Decimal,
    unit: str,
    *,
    reference_type: str,
    reference_id: UUID | None,
    txn_type: str = "sale_out",
    user_id: UUID | None = None,
    note: str | None = None,
    allow_negative: bool = False,
) -> InventoryTxn:
    """Remove stock (positive `quantity` in the PRIMARY unit), valued at avg_cost."""
    quantity = Decimal(str(quantity))
    inv = _locked(db, business_id, product_id)
    if not allow_negative and inv.qty_primary < quantity:
        raise InsufficientStock(
            f"Insufficient stock for product {product_id}: available={inv.qty_primary}, requested={quantity}"
        )
    inv.qty_primary -= quantity
    txn = InventoryTxn(
        id=uuid4(),
        business_id=business_id,
        inventory_id=inv.id,
        txn_type=txn_type,
        qty_change=-quantity,
        unit_cost=inv.avg_cost,
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
    business_id: UUID,
    product_id: UUID,
    quantity: Decimal,
    unit: str,
    *,
    reference_type: str = "wastage",
    reference_id: UUID | None = None,
    user_id: UUID | None = None,
    note: str | None = None,
) -> InventoryTxn:
    """Write off damaged/short stock at the current average cost."""
    return stock_out(
        db, business_id, product_id, quantity, unit,
        reference_type=reference_type, reference_id=reference_id, txn_type="wastage",
        user_id=user_id, note=note or "Damaged/short on arrival", allow_negative=True,
    )


def adjust_stock(
    db: Session,
    business_id: UUID,
    product_id: UUID,
    actual_qty: Decimal,
    reason: str,
    *,
    user_id: UUID | None = None,
    note: str | None = None,
    reference_id: UUID | None = None,
) -> InventoryTxn:
    """Physical count: set stock to `actual_qty` (primary unit) and log the difference."""
    inv = _locked(db, business_id, product_id)
    product = db.get(Product, product_id)
    actual_qty = Decimal(str(actual_qty))
    difference = actual_qty - inv.qty_primary
    inv.qty_primary = actual_qty
    text = f"Physical count adjustment: {reason}"
    if note:
        text += f" — {note}"
    txn = InventoryTxn(
        id=uuid4(),
        business_id=business_id,
        inventory_id=inv.id,
        txn_type="adjustment",
        qty_change=difference,
        unit_cost=inv.avg_cost,
        unit=product.primary_unit if product else "unit",
        reference_type="stock_count",
        reference_id=reference_id,
        note=text,
        created_by=user_id,
    )
    db.add(txn)
    return txn
