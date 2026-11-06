from datetime import date
from decimal import Decimal

from app.services.gst_engine import lookup_gst_rate, lookup_hsn, round_to_rupee
from app.services.numbering import financial_year


def test_gst2_rate_change_is_date_effective():
    assert lookup_gst_rate("3401", date(2025, 9, 21)) == Decimal("18")
    assert lookup_gst_rate("34011110", date(2025, 9, 22)) == Decimal("5")
    assert lookup_gst_rate("3305", date(2026, 1, 1)) == Decimal("5")
    assert lookup_gst_rate("3306", date(2026, 1, 1)) == Decimal("5")
    assert lookup_gst_rate("3402", date(2026, 1, 1)) == Decimal("18")


def test_longest_prefix_wins():
    assert lookup_gst_rate("21069099", date(2026, 1, 1)) == Decimal("5")
    pan_masala = lookup_hsn("21069020", date(2026, 1, 1))
    assert pan_masala.rate == Decimal("28") and pan_masala.requires_ca_review


def test_unknown_hsn():
    assert lookup_gst_rate("9999") is None
    assert lookup_gst_rate("") is None


def test_round_to_rupee():
    assert round_to_rupee(Decimal("117.17")) == (Decimal("117.00"), Decimal("-0.17"))
    assert round_to_rupee(Decimal("117.50")) == (Decimal("118.00"), Decimal("0.50"))


def test_financial_year():
    assert financial_year(date(2026, 3, 31)) == "2526"
    assert financial_year(date(2026, 4, 1)) == "2627"
    assert financial_year(date(2099, 12, 1)) == "9900"


def test_hsn_lookup_endpoint(client, owner):
    r = owner.get("/api/v1/products/hsn-lookup", params={"hsn_code": "3401", "on_date": "2025-09-01"})
    assert r.json()["gst_rate"] == "18"
    r = owner.get("/api/v1/products/hsn-lookup", params={"hsn_code": "3401"})
    assert r.json()["gst_rate"] == "5"
