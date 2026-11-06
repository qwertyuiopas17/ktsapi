"""
KTS — GST Calculation Engine
Configurable rules engine (not hard-coded) for Indian GST computation.
Supports the post-Sept 2025 reformed rates: 0%, 5%, 18%, 40%.
"""
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# GST Rate Map — updated Sept 2025 reform
# This is the configurable layer. When GOI changes rates, update HERE only.
# ---------------------------------------------------------------------------

GST_SLABS = {
    Decimal("0"): "Nil — essentials (fresh produce, milk, bread)",
    Decimal("5"): "Mass consumption — packaged food, sugar, tea, edible oil",
    Decimal("18"): "Standard — electronics, textiles, machinery, services",
    Decimal("40"): "Luxury/sin — tobacco, aerated drinks, high-end vehicles",
    Decimal("3"): "Special — gold, diamonds",
}

VALID_GST_RATES = set(GST_SLABS.keys())


@dataclass
class GstBreakdown:
    """Result of a GST calculation on a single line item."""
    subtotal: Decimal       # pre-tax amount
    cgst: Decimal           # Central GST (intra-state only)
    sgst: Decimal           # State GST (intra-state only)
    igst: Decimal           # Integrated GST (inter-state only)
    total: Decimal          # subtotal + all GST
    is_inter_state: bool
    gst_rate: Decimal

    @property
    def total_gst(self) -> Decimal:
        return self.cgst + self.sgst + self.igst


def _round2(value: Decimal) -> Decimal:
    """Round to 2 decimal places (standard for Indian invoicing)."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_line_gst(
    amount: Decimal,
    gst_rate: Decimal,
    supplier_state: str,
    customer_state: str,
) -> GstBreakdown:
    """
    Calculate GST for a single line item.

    Args:
        amount: Pre-tax amount (qty × rate − discount)
        gst_rate: GST percentage (0, 5, 18, 40)
        supplier_state: 2-digit state code of the seller/business
        customer_state: 2-digit state code of the buyer/customer

    Returns:
        GstBreakdown with all computed values
    """
    amount = Decimal(str(amount))
    gst_rate = Decimal(str(gst_rate))

    is_inter_state = supplier_state != customer_state
    gst_amount = _round2(amount * gst_rate / Decimal("100"))

    if is_inter_state:
        return GstBreakdown(
            subtotal=_round2(amount),
            cgst=Decimal("0"),
            sgst=Decimal("0"),
            igst=gst_amount,
            total=_round2(amount + gst_amount),
            is_inter_state=True,
            gst_rate=gst_rate,
        )
    else:
        half = _round2(gst_amount / Decimal("2"))
        # Handle rounding: if 2×half ≠ gst_amount, adjust CGST
        cgst = half
        sgst = gst_amount - half  # ensures cgst + sgst == gst_amount exactly
        return GstBreakdown(
            subtotal=_round2(amount),
            cgst=cgst,
            sgst=sgst,
            igst=Decimal("0"),
            total=_round2(amount + gst_amount),
            is_inter_state=False,
            gst_rate=gst_rate,
        )


def calculate_bill_gst(
    items: list[dict],
    supplier_state: str,
    customer_state: str,
) -> dict:
    """
    Calculate GST for an entire bill (multiple line items, potentially
    different GST rates per item).

    Args:
        items: list of dicts with keys: amount, gst_rate
        supplier_state: business state code
        customer_state: customer state code

    Returns:
        dict with: subtotal, total_cgst, total_sgst, total_igst, grand_total,
                   is_inter_state, items (list of GstBreakdown per item)
    """
    total_subtotal = Decimal("0")
    total_cgst = Decimal("0")
    total_sgst = Decimal("0")
    total_igst = Decimal("0")
    item_breakdowns = []

    for item in items:
        breakdown = calculate_line_gst(
            amount=item["amount"],
            gst_rate=item["gst_rate"],
            supplier_state=supplier_state,
            customer_state=customer_state,
        )
        total_subtotal += breakdown.subtotal
        total_cgst += breakdown.cgst
        total_sgst += breakdown.sgst
        total_igst += breakdown.igst
        item_breakdowns.append(breakdown)

    return {
        "subtotal": _round2(total_subtotal),
        "total_cgst": _round2(total_cgst),
        "total_sgst": _round2(total_sgst),
        "total_igst": _round2(total_igst),
        "grand_total": _round2(total_subtotal + total_cgst + total_sgst + total_igst),
        "is_inter_state": supplier_state != customer_state,
        "items": item_breakdowns,
    }


# ---------------------------------------------------------------------------
# HSN → GST Rate Lookup (subset — full DB loaded from hsn_codes.json)
# ---------------------------------------------------------------------------

# Common HSN codes for distributor products — covers 80%+ of use cases
HSN_GST_MAP = {
    # 0% — Nil
    "0713": Decimal("0"),   # Dried leguminous vegetables (unbranded)
    "0401": Decimal("0"),   # Fresh milk
    "0702": Decimal("0"),   # Tomatoes
    "1006": Decimal("0"),   # Rice (unbranded)

    # 5%
    "1701": Decimal("5"),   # Sugar
    "1901": Decimal("5"),   # Food preparations (branded)
    "0902": Decimal("5"),   # Tea
    "1515": Decimal("5"),   # Edible oil
    "1101": Decimal("5"),   # Wheat flour (atta)
    "1006.30": Decimal("5"), # Rice (branded/packaged)
    "0713.10": Decimal("5"), # Branded dried peas
    "2106": Decimal("5"),   # Food preparations NES

    # 18%
    "7317": Decimal("18"),  # Nails, tacks, staples (steel nails)
    "3401": Decimal("18"),  # Soap
    "3402": Decimal("18"),  # Detergents
    "8414": Decimal("18"),  # Fans, blowers
    "8418": Decimal("18"),  # Refrigerators
    "8516": Decimal("18"),  # Electric heaters, irons

    # 40%
    "2402": Decimal("40"),  # Cigars, cigarettes
    "2202": Decimal("40"),  # Aerated drinks
}


def lookup_gst_rate(hsn_code: str) -> Decimal | None:
    """
    Look up GST rate from HSN code.
    Returns None if HSN code not found (user must set manually).
    Checks exact match first, then partial (first 4 digits).
    """
    if not hsn_code:
        return None

    # Exact match
    if hsn_code in HSN_GST_MAP:
        return HSN_GST_MAP[hsn_code]

    # Try first 4 digits
    prefix = hsn_code[:4]
    if prefix in HSN_GST_MAP:
        return HSN_GST_MAP[prefix]

    return None
