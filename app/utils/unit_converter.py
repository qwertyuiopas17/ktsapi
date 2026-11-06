"""
KTS — Unit Converter
Handles Bag ↔ Kg, Case ↔ Piece, Litre ↔ ml type conversions.
The conversion_factor on a Product defines the relationship:
    1 [primary_unit] = [conversion_factor] × [secondary_unit]
    e.g. 1 Bag = 50 Kg → conversion_factor = 50
"""
from decimal import Decimal, ROUND_HALF_UP


def primary_to_secondary(qty_primary: Decimal, conversion_factor: Decimal) -> Decimal:
    """Convert primary unit qty to secondary unit qty."""
    return (qty_primary * conversion_factor).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def secondary_to_primary(qty_secondary: Decimal, conversion_factor: Decimal) -> Decimal:
    """Convert secondary unit qty to primary unit qty."""
    if conversion_factor == 0:
        return qty_secondary
    return (qty_secondary / conversion_factor).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def format_stock_display(
    qty_primary: Decimal,
    primary_unit: str,
    secondary_unit: str | None,
    conversion_factor: Decimal,
) -> str:
    """
    Format stock for display.
    e.g., "10 Bags (500 Kg)" or "37.5 Kg" (if no secondary unit).
    """
    if secondary_unit and conversion_factor != 1:
        qty_secondary = primary_to_secondary(qty_primary, conversion_factor)
        return f"{qty_primary} {primary_unit} ({qty_secondary} {secondary_unit})"
    return f"{qty_primary} {primary_unit}"
