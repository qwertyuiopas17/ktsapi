"""Sprint 2 — Full E2E test: Expenses + Bill PDF + WhatsApp share + OCR scan endpoint."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx
import json

BASE = "http://localhost:8000"
c = httpx.Client(base_url=BASE, timeout=30)

print("=" * 60)
print("SPRINT 2 — E2E TEST")
print("=" * 60)

# ──────────────── Setup ────────────────
# 1. Create products
print("\n[1] Creating products...")
products = []
for p in [
    {"name": "Toor Dal Premium", "shortcode": "TDP", "hsn_code": "0713", "gst_rate": 5,
     "primary_unit": "Kg", "secondary_unit": "Bag", "conversion_factor": 50,
     "purchase_price": 90, "sell_price_retail": 110, "low_stock_threshold": 10},
    {"name": "Mustard Oil", "shortcode": "MO", "hsn_code": "1514", "gst_rate": 5,
     "primary_unit": "Litre", "secondary_unit": "Can", "conversion_factor": 15,
     "purchase_price": 140, "sell_price_retail": 170, "low_stock_threshold": 5},
    {"name": "Wheat Flour Atta", "shortcode": "WFA", "hsn_code": "1101", "gst_rate": 0,
     "primary_unit": "Kg", "secondary_unit": "Bag", "conversion_factor": 10,
     "purchase_price": 28, "sell_price_retail": 35, "low_stock_threshold": 20},
]:
    r = c.post("/api/v1/products", json=p)
    assert r.status_code == 201, f"Product create failed: {r.text}"
    products.append(r.json())
print(f"   Created {len(products)} products")

# 2. Create customer
print("\n[2] Creating customer...")
r = c.post("/api/v1/customers", json={
    "name": "Sharma General Store", "phone": "+919876543210",
    "address": "Main Bazaar, Rohtak", "state_code": "06",
    "credit_limit": 50000,
})
assert r.status_code == 201
customer = r.json()
cust_id = customer["id"]
print(f"   Customer: {customer['name']} ({cust_id})")

# 3. Create supplier
print("\n[3] Creating supplier...")
r = c.post("/api/v1/companies", json={
    "name": "Rajdhani Foods Pvt Ltd", "gstin": "06AABCR1234M1Z5",
    "contact_person": "Mr. Verma", "phone": "+919988776655",
    "address": "Industrial Area, Sonepat", "state_code": "06",
})
assert r.status_code == 201
company = r.json()
comp_id = company["id"]
print(f"   Supplier: {company['name']} ({comp_id})")

# 4. Purchase stock
print("\n[4] Creating purchase (stock in)...")
r = c.post("/api/v1/purchases", json={
    "company_id": comp_id,
    "invoice_number": "RF-2026-0881",
    "items": [
        {"product_id": products[0]["id"], "quantity": 5, "unit": "Bag", "rate": 4500, "gst_rate": 5},
        {"product_id": products[1]["id"], "quantity": 10, "unit": "Can", "rate": 2100, "gst_rate": 5},
        {"product_id": products[2]["id"], "quantity": 20, "unit": "Bag", "rate": 280, "gst_rate": 0},
    ],
    "payment_status": "partial",
    "amount_paid": 20000,
})
assert r.status_code == 201
purchase = r.json()
print(f"   Purchase total: Rs {purchase['total_amount']}")

# ──────────────── Sprint 2 Tests ────────────────

# 5. Create bill (to test PDF + WhatsApp)
print("\n[5] Creating sale bill...")
r = c.post("/api/v1/bills", json={
    "customer_id": cust_id,
    "bill_type": "invoice",
    "items": [
        {"product_id": products[0]["id"], "quantity": 2, "unit": "Bag", "rate": 5500},
        {"product_id": products[1]["id"], "quantity": 3, "unit": "Can", "rate": 2550},
        {"product_id": products[2]["id"], "quantity": 5, "unit": "Bag", "rate": 350},
    ],
    "payment_status": "partial",
    "amount_paid": 10000,
    "payment_mode": "cash",
})
assert r.status_code == 201, f"Bill failed: {r.text}"
bill = r.json()
bill_id = bill["id"]
print(f"   Bill #{bill['bill_number']}: Rs {bill['total_amount']}")
print(f"   CGST: {bill['cgst_amount']}, SGST: {bill['sgst_amount']}, IGST: {bill['igst_amount']}")

# 6. Download bill PDF (A4)
print("\n[6] Downloading bill PDF (A4)...")
r = c.get(f"/api/v1/bills/{bill_id}/pdf?format=a4")
assert r.status_code == 200, f"PDF failed: {r.status_code} {r.text}"
assert r.headers["content-type"] == "application/pdf"
pdf_size = len(r.content)
print(f"   PDF size: {pdf_size:,} bytes")
assert pdf_size > 100, "PDF too small, likely empty"

# 7. Download bill PDF (thermal)
print("\n[7] Downloading bill PDF (thermal)...")
r = c.get(f"/api/v1/bills/{bill_id}/pdf?format=thermal")
assert r.status_code == 200
thermal_size = len(r.content)
print(f"   Thermal PDF size: {thermal_size:,} bytes")

# 8. WhatsApp share link
print("\n[8] Getting WhatsApp share link...")
r = c.get(f"/api/v1/bills/{bill_id}/share/whatsapp")
assert r.status_code == 200
wa = r.json()
print(f"   WhatsApp link: {wa['wa_link'][:80]}...")
print(f"   Customer phone: {wa['customer_phone']}")
assert "wa.me" in wa["wa_link"]
assert wa["bill_number"] == bill["bill_number"]

# 9. Create expenses
print("\n[9] Creating expenses...")
expenses = []
for exp in [
    {"category": "fuel", "amount": 2500, "note": "Delivery truck diesel"},
    {"category": "salary", "amount": 15000, "note": "Helper salary - Aug"},
    {"category": "rent", "amount": 8000, "payment_mode": "bank_transfer"},
    {"category": "packaging", "amount": 500, "note": "Carry bags"},
    {"category": "electricity", "amount": 3200, "payment_mode": "upi"},
]:
    r = c.post("/api/v1/expenses", json=exp)
    assert r.status_code == 201, f"Expense failed: {r.text}"
    expenses.append(r.json())
print(f"   Created {len(expenses)} expenses")

# 10. List expenses
print("\n[10] Listing expenses...")
r = c.get("/api/v1/expenses")
assert r.status_code == 200
exp_list = r.json()
print(f"   Total expenses: {exp_list['total']}, Amount: Rs {exp_list['total_amount']}")
assert exp_list["total"] == 5
assert float(exp_list["total_amount"]) == 29200

# 11. Expense summary
print("\n[11] Expense summary (P&L breakdown)...")
r = c.get("/api/v1/expenses/summary?days=30")
assert r.status_code == 200
summary = r.json()
print(f"   Period: {summary['period_start']} to {summary['period_end']}")
print(f"   Total: Rs {summary['total']}")
for cat, amt in sorted(summary["by_category"].items()):
    print(f"     {cat}: Rs {amt}")

# 12. Filter expenses by category
print("\n[12] Filter expenses (fuel only)...")
r = c.get("/api/v1/expenses?category=fuel")
assert r.status_code == 200
fuel = r.json()
assert fuel["total"] == 1
print(f"   Fuel expenses: {fuel['total']}, Amount: Rs {fuel['total_amount']}")

# 13. OCR scan endpoint (test structure, not actual OCR)
print("\n[13] Testing OCR scan endpoint...")
# Create a fake image to test the endpoint accepts files
import io
fake_img = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # minimal PNG header
r = c.post("/api/v1/purchases/scan", files={"file": ("test.png", io.BytesIO(fake_img), "image/png")})
print(f"   OCR endpoint: status={r.status_code}")
# Will return error (no valid image) but endpoint is reachable
assert r.status_code in (200, 422), f"OCR endpoint failed: {r.status_code}"

# 14. Dashboard (should include expenses)
print("\n[14] Dashboard...")
r = c.get("/api/v1/dashboard")
assert r.status_code == 200
dash = r.json()
print(f"   Today sales: Rs {dash['today_sales']}")
print(f"   Today purchases: Rs {dash['today_purchases']}")
print(f"   Today expenses: Rs {dash['today_expenses']}")
print(f"   Low stock: {dash['low_stock_count']}")
print(f"   Overdue: {dash['overdue_count']}")

# 15. JWT auth test
print("\n[15] JWT auth service test...")
from app.services.auth_service import create_token, decode_token
token = create_token(
    "00000000-0000-0000-0000-000000000001",
    "00000000-0000-0000-0000-000000000001",
    "+919876543210", "owner"
)
payload = decode_token(token)
assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
assert payload["role"] == "owner"
print(f"   JWT: sub={payload['sub'][:20]}..., role={payload['role']}")

print("\n" + "=" * 60)
print("ALL SPRINT 2 TESTS PASSED!")
print("=" * 60)
print(f"\nNew endpoints added:")
print(f"  POST   /api/v1/expenses         - Create expense")
print(f"  GET    /api/v1/expenses          - List with filters")
print(f"  GET    /api/v1/expenses/summary  - P&L category breakdown")
print(f"  GET    /api/v1/expenses/{{id}}     - Get single expense")
print(f"  DELETE /api/v1/expenses/{{id}}     - Delete expense")
print(f"  GET    /api/v1/bills/{{id}}/pdf    - Download invoice PDF")
print(f"  GET    /api/v1/bills/{{id}}/share/whatsapp - WhatsApp share")
print(f"  POST   /api/v1/purchases/scan    - OCR invoice scanner")
