"""
KTS — GST Calculation Engine
Configurable rules engine (not hard-coded) for Indian GST computation.
Supports the GST 2.0 slabs (0%, 5%, 18%, 40%, effective 22 Sep 2025) plus
the legacy 12%/28% rates needed for older documents and tobacco.
"""
import json
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path


# ---------------------------------------------------------------------------
# GST Rate Map — updated Sept 2025 reform
# This is the configurable layer. When GOI changes rates, update HERE only.
# ---------------------------------------------------------------------------

GST_SLABS = {
    Decimal("0"): "Nil — essentials (fresh produce, milk, bread)",
    Decimal("5"): "Mass consumption — packaged food, sugar, tea, edible oil",
    Decimal("18"): "Standard — electronics, textiles, machinery, services",
    Decimal("40"): "Luxury/sin — aerated drinks, high-end vehicles",
    Decimal("3"): "Special — gold, diamonds",
    Decimal("0.25"): "Special — rough diamonds",
    Decimal("12"): "Legacy (pre GST 2.0)",
    Decimal("28"): "Legacy; tobacco and pan masala until the compensation cess ends",
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


def round_to_rupee(amount: Decimal) -> tuple[Decimal, Decimal]:
    """Invoice round-off to the nearest rupee. Returns (rounded_total, round_off)."""
    rounded = Decimal(amount).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return rounded.quantize(Decimal("0.01")), (rounded - Decimal(amount)).quantize(Decimal("0.01"))


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
# HSN → GST rate lookup with effective dates (data/hsn_rates.json)
# ---------------------------------------------------------------------------

_RATES_FILE = Path(__file__).resolve().parents[2] / "data" / "hsn_rates.json"


@dataclass(frozen=True)
class HsnRate:
    hsn_prefix: str
    rate: Decimal
    cess_rate: Decimal
    effective_from: date
    effective_to: date | None
    description: str
    note: str | None = None
    requires_ca_review: bool = False

    def active_on(self, on: date) -> bool:
        return self.effective_from <= on and (self.effective_to is None or on <= self.effective_to)


@lru_cache(maxsize=1)
def load_hsn_rates() -> tuple[HsnRate, ...]:
    raw = json.loads(_RATES_FILE.read_text(encoding="utf-8"))["rates"]
    return tuple(
        HsnRate(
            hsn_prefix=r["hsn_prefix"],
            rate=Decimal(str(r["rate"])),
            cess_rate=Decimal(str(r.get("cess_rate") or 0)),
            effective_from=date.fromisoformat(r["effective_from"]),
            effective_to=date.fromisoformat(r["effective_to"]) if r.get("effective_to") else None,
            description=r.get("description", ""),
            note=r.get("note"),
            requires_ca_review=bool(r.get("requires_ca_review", False)),
        )
        for r in raw
    )


def lookup_hsn(hsn_code: str | None, on_date: date | None = None) -> HsnRate | None:
    """Longest HSN prefix match that is in force on `on_date` (default: today)."""
    if not hsn_code:
        return None
    code = hsn_code.replace(".", "").replace(" ", "")
    on = on_date or date.today()
    best: HsnRate | None = None
    for r in load_hsn_rates():
        if code.startswith(r.hsn_prefix) and r.active_on(on):
            if best is None or len(r.hsn_prefix) > len(best.hsn_prefix):
                best = r
    return best


def lookup_gst_rate(hsn_code: str | None, on_date: date | None = None) -> Decimal | None:
    """GST rate for an HSN code on a date, or None if unknown (user must set it)."""
    found = lookup_hsn(hsn_code, on_date)
    return found.rate if found else None
