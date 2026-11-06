from decimal import Decimal

from tests.conftest import (
    bill, create_company, create_customer, create_product, make_owner, purchase,
)

D = Decimal


def _stocked(owner, qty=20, rate=100, **product):
    p = create_product(owner, **product)
    c = create_company(owner)
    purchase(owner, c["id"], p["id"], qty, rate)
    return p, c


def _line(p, qty=1, unit="Box", rate=150, **kw):
    return {"product_id": p["id"], "quantity": qty, "unit": unit, "rate": rate, **kw}


# ─── numbering ──────────────────────────────────────────────
def test_fy_series_numbering_per_business(client, owner):
    other = make_owner(client, "Other")
    p, _ = _stocked(owner)
    q, _ = _stocked(other)
    cust, cust2 = create_customer(owner), create_customer(other)

    n1 = bill(owner, cust["id"], [_line(p)])["bill_number"]
    n2 = bill(owner, cust["id"], [_line(p)])["bill_number"]
    m1 = bill(other, cust2["id"], [_line(q)])["bill_number"]
    assert (n1, n2) == ("INV/2627/00001", "INV/2627/00002")
    assert m1 == "INV/2627/00001"  # same number is fine in another business
    assert len(n1) <= 16


def test_new_financial_year_restarts_series(client, owner):
    p, _ = _stocked(owner)
    cust = create_customer(owner)
    assert bill(owner, cust["id"], [_line(p)], bill_date="2027-03-31")["bill_number"] == "INV/2627/00001"
    assert bill(owner, cust["id"], [_line(p)], bill_date="2027-04-01")["bill_number"] == "INV/2728/00001"


def test_challan_has_its_own_series(client, owner):
    p, _ = _stocked(owner)
    cust = create_customer(owner)
    bill(owner, cust["id"], [_line(p)])
    assert bill(owner, cust["id"], [_line(p)], bill_type="challan")["bill_number"] == "DC/2627/00001"


def test_credit_note_not_accepted_on_sale_endpoint(client, owner):
    p, _ = _stocked(owner)
    cust = create_customer(owner)
    bill(owner, cust["id"], [_line(p)], bill_type="credit_note", expect=422)


def test_failed_bill_does_not_consume_a_number(client, owner):
    p, _ = _stocked(owner, qty=1)
    cust = create_customer(owner)
    bill(owner, cust["id"], [_line(p, qty=5)], expect=400)  # insufficient stock
    assert bill(owner, cust["id"], [_line(p)])["bill_number"] == "INV/2627/00001"


# ─── tax + round-off ────────────────────────────────────────
def test_intra_state_gst_and_round_off(client, owner):
    p, _ = _stocked(owner, gst_rate=18)
    cust = create_customer(owner, state_code="19")
    b = bill(owner, cust["id"], [_line(p, qty=1, rate="99.30")])
    # 99.30 + 18% = 117.174 -> CGST 8.94 + SGST 8.93 = 17.87 -> 117.17 -> rounded 117
    assert D(b["cgst_amount"]) + D(b["sgst_amount"]) == D("17.87")
    assert D(b["round_off"]) == D("-0.17")
    assert D(b["total_amount"]) == D("117.00")
    assert D(b["igst_amount"]) == 0


def test_inter_state_uses_igst(client, owner):
    p, _ = _stocked(owner, gst_rate=5)
    cust = create_customer(owner, state_code="20")
    b = bill(owner, cust["id"], [_line(p, qty=2, rate=100)])
    assert D(b["igst_amount"]) == D("10.00")
    assert D(b["cgst_amount"]) == 0


def test_pdf_and_whatsapp(client, owner):
    p, _ = _stocked(owner)
    cust = create_customer(owner)
    b = bill(owner, cust["id"], [_line(p)])
    r = owner.get(f"/api/v1/bills/{b['id']}/pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert "INV-2627-00001.pdf" in r.headers["content-disposition"]
    wa = owner.get(f"/api/v1/bills/{b['id']}/share/whatsapp").json()
    assert "INV/2627/00001" in wa["message"]


# ─── stock + cost ───────────────────────────────────────────
def test_moving_average_cost_basis(client, owner):
    p = create_product(owner)  # Box primary, 10 Piece per Box
    c = create_company(owner)
    purchase(owner, c["id"], p["id"], 10, 100)
    purchase(owner, c["id"], p["id"], 10, 130)
    prod = owner.get(f"/api/v1/products/{p['id']}").json()
    assert D(prod["avg_cost"]) == D("115")
    assert D(prod["stock_value"]) == D("2300.00")

    cust = create_customer(owner)
    b = bill(owner, cust["id"], [_line(p, qty=2, rate=150), _line(p, qty=5, unit="Piece", rate=16)])
    assert D(b["items"][0]["cost_basis"]) == D("115")      # per Box
    assert D(b["items"][1]["cost_basis"]) == D("11.5")     # per Piece
    # 20 boxes - 2 - 0.5 = 17.5 left, average unchanged by sales
    prod = owner.get(f"/api/v1/products/{p['id']}").json()
    assert D(prod["current_stock"]) == D("17.5")
    assert D(prod["avg_cost"]) == D("115")


def test_purchase_discount_and_secondary_unit_feed_landed_cost(client, owner):
    p = create_product(owner)
    c = create_company(owner)
    # 100 pieces (=10 boxes) @ ₹12/piece, 10% discount -> 1080 ex-GST -> ₹108 per box
    purchase(owner, c["id"], p["id"], 100, 12, unit="Piece", discount_pct=10)
    prod = owner.get(f"/api/v1/products/{p['id']}").json()
    assert D(prod["current_stock"]) == D("10")
    assert D(prod["avg_cost"]) == D("108")


def test_damaged_qty_is_written_off_not_double_counted(client, owner):
    p = create_product(owner)
    c = create_company(owner)
    purchase(owner, c["id"], p["id"], 10, 100, damaged_qty=2)
    prod = owner.get(f"/api/v1/products/{p['id']}").json()
    assert D(prod["current_stock"]) == D("8")
    moves = owner.get(f"/api/v1/inventory/{p['id']}/movements").json()
    assert sorted(m["txn_type"] for m in moves) == ["purchase_in", "wastage"]


def test_insufficient_stock_counts_duplicate_lines(client, owner):
    p, _ = _stocked(owner, qty=3)
    cust = create_customer(owner)
    bill(owner, cust["id"], [_line(p, qty=2), _line(p, qty=2)], expect=400)
    b = bill(owner, cust["id"], [_line(p, qty=2), _line(p, qty=1)])
    assert len(b["items"]) == 2
    assert D(owner.get(f"/api/v1/products/{p['id']}").json()["current_stock"]) == 0


def test_stock_adjustment_batch(client, owner):
    p, _ = _stocked(owner, qty=10)
    q = create_product(owner)
    r = owner.post("/api/v1/inventory/adjustments", json={
        "reason": "stock_count", "note": "Monthly count",
        "items": [{"product_id": p["id"], "actual_qty": 9}, {"product_id": q["id"], "actual_qty": 0}],
    })
    assert r.status_code == 201, r.text
    diffs = {i["product_id"]: D(i["difference"]) for i in r.json()["items"]}
    assert diffs[p["id"]] == D("-1")
    moves = owner.get(f"/api/v1/inventory/{p['id']}/movements").json()
    assert moves[0]["txn_type"] == "adjustment"


def test_opening_stock_sets_cost(client, owner):
    p = create_product(owner)
    r = owner.post("/api/v1/inventory/adjustments", json={
        "reason": "opening_stock", "items": [{"product_id": p["id"], "actual_qty": 12, "unit_cost": 90}],
    })
    assert r.status_code == 201
    prod = owner.get(f"/api/v1/products/{p['id']}").json()
    assert D(prod["current_stock"]) == 12 and D(prod["avg_cost"]) == 90


# ─── credit policy ──────────────────────────────────────────
def test_credit_limit_block_and_warn(client, owner):
    p, _ = _stocked(owner)
    cust = create_customer(owner, credit_limit=100)
    bill(owner, cust["id"], [_line(p, rate=150)], expect=400)  # default policy: block
    # A paid bill is never blocked
    bill(owner, cust["id"], [_line(p, rate=150)], payment_status="paid", payment_mode="cash")

    owner.put("/api/v1/auth/business", json={"name": "Kolkata Traders", "state_code": "19", "credit_policy": "warn"})
    b = bill(owner, cust["id"], [_line(p, rate=150)])
    assert b["warnings"] and "Credit limit exceeded" in b["warnings"][0]


def test_amount_paid_cannot_exceed_total(client, owner):
    p, _ = _stocked(owner)
    cust = create_customer(owner)
    bill(owner, cust["id"], [_line(p, rate=100)], amount_paid=10_000, payment_status="partial", expect=400)


# ─── cancellation ───────────────────────────────────────────
def test_cancel_reverses_stock_and_ledger(client, owner):
    p, _ = _stocked(owner, qty=10, rate=100)
    cust = create_customer(owner)
    b = bill(owner, cust["id"], [_line(p, qty=4, rate=150)])
    assert D(owner.get(f"/api/v1/customers/{cust['id']}").json()["outstanding"]) == D(b["total_amount"])

    r = owner.post(f"/api/v1/bills/{b['id']}/cancel", json={"reason": "Wrong customer"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"

    prod = owner.get(f"/api/v1/products/{p['id']}").json()
    assert D(prod["current_stock"]) == 10
    assert D(prod["avg_cost"]) == 100
    assert D(owner.get(f"/api/v1/customers/{cust['id']}").json()["outstanding"]) == 0
    ledger = owner.get(f"/api/v1/ledger/customer/{cust['id']}").json()["entries"]
    assert {e["entry_type"] for e in ledger} == {"sale", "sale_cancel"}

    assert owner.post(f"/api/v1/bills/{b['id']}/cancel", json={"reason": "again"}).status_code == 409
    # Number is not reused
    assert bill(owner, cust["id"], [_line(p)])["bill_number"] == "INV/2627/00002"
    # Cancelled bills still exist and can be filtered
    assert owner.get("/api/v1/bills?status=cancelled").json()["total"] == 1


def test_cancelled_bills_excluded_from_dashboard(client, owner):
    from datetime import date

    p, _ = _stocked(owner)
    cust = create_customer(owner)
    b = bill(owner, cust["id"], [_line(p, rate=100)], bill_date=date.today().isoformat())
    assert D(owner.get("/api/v1/dashboard").json()["today_sales"]) == D(b["total_amount"])
    owner.post(f"/api/v1/bills/{b['id']}/cancel", json={"reason": "test"})
    assert D(owner.get("/api/v1/dashboard").json()["today_sales"]) == 0


def test_customer_with_history_cannot_be_deleted(client, owner):
    p, c = _stocked(owner)
    cust = create_customer(owner)
    bill(owner, cust["id"], [_line(p)])
    assert owner.delete(f"/api/v1/customers/{cust['id']}").status_code == 409
    assert owner.delete(f"/api/v1/companies/{c['id']}").status_code == 409
    fresh = create_customer(owner)
    assert owner.delete(f"/api/v1/customers/{fresh['id']}").status_code == 204


def test_billing_requires_business_setup(client):
    from tests.conftest import login, random_phone

    new_owner = login(client, random_phone())
    p = create_product(new_owner)
    cust = create_customer(new_owner)
    r = new_owner.post("/api/v1/bills", json={"customer_id": cust["id"], "items": [_line(p)]})
    assert r.status_code == 400
