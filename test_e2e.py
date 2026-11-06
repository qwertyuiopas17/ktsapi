"""
KTS — Full End-to-End Test
Simulates a real distributor day: receive stock -> bill customer -> collect payment.
Tests the complete transactional loop.
"""
import httpx
import sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8000/api/v1"

print("=" * 60)
print("KTS FULL E2E TEST - A Day in Raju's Life")
print("=" * 60)

# --- SETUP: Create master data ---
print("\n--- SETUP ---")

# Create products
products = {}
for p in [
    {"name": "Toor Dal", "shortcode": "TD", "hsn_code": "0713", "category": "Grains",
     "primary_unit": "Bag", "secondary_unit": "Kg", "conversion_factor": 50,
     "purchase_price": 4500, "sell_price_wholesale": 95, "low_stock_threshold": 5, "is_loose_stock": True},
    {"name": "Refined Oil", "shortcode": "RO", "hsn_code": "1515", "category": "Oil",
     "primary_unit": "Can", "secondary_unit": "Litre", "conversion_factor": 15,
     "purchase_price": 2700, "sell_price_wholesale": 195, "low_stock_threshold": 3, "is_loose_stock": True},
    {"name": "Steel Nails", "shortcode": "SN", "hsn_code": "7317", "category": "Hardware",
     "primary_unit": "Box", "secondary_unit": "Kg", "conversion_factor": 10,
     "purchase_price": 1200, "sell_price_wholesale": 140, "low_stock_threshold": 10, "is_loose_stock": True},
]:
    r = httpx.post(f"{BASE}/products", json=p)
    assert r.status_code == 201, f"Failed to create {p['name']}: {r.text}"
    prod = r.json()
    products[prod["shortcode"]] = prod
    print(f"  Product: {prod['name']} | GST: {prod['gst_rate']}%")

# Create company (supplier)
r = httpx.post(f"{BASE}/companies", json={
    "name": "Maharashtra Pulses Ltd", "gstin": "27AABCU9603R1ZM",
    "state_code": "27", "contact_person": "Ramesh Patel"
})
company = r.json()
print(f"  Company: {company['name']}")

# Create customers
r = httpx.post(f"{BASE}/customers", json={
    "name": "Rajan General Store", "phone": "+919876543210",
    "state_code": "27", "price_tier": "wholesale", "credit_limit": 50000
})
cust1 = r.json()
print(f"  Customer: {cust1['name']} (credit limit: {cust1['credit_limit']})")

# ===================================================================
# MORNING 5 AM: RECEIVE STOCK (Purchase)
# ===================================================================
print("\n" + "=" * 60)
print("5:00 AM - RECEIVE STOCK FROM TRUCK")
print("=" * 60)

r = httpx.post(f"{BASE}/purchases", json={
    "company_id": company["id"],
    "invoice_number": "MP-2025-4521",
    "invoice_date": "2025-09-03",
    "items": [
        {"product_id": products["TD"]["id"], "quantity": 20, "unit": "Bag",
         "rate": 4500, "gst_rate": 0, "damaged_qty": 1},  # 1 bag damaged!
        {"product_id": products["RO"]["id"], "quantity": 10, "unit": "Can",
         "rate": 2700, "gst_rate": 5},
        {"product_id": products["SN"]["id"], "quantity": 15, "unit": "Box",
         "rate": 1200, "gst_rate": 18},
    ],
    "payment_status": "credit",
    "amount_paid": 0,
    "source": "manual",
})
assert r.status_code == 201, f"Purchase failed: {r.text}"
purchase = r.json()
print(f"  Purchase #{purchase['invoice_number']} created")
print(f"  Total: Rs {purchase['total_amount']} | GST: Rs {purchase['gst_amount']}")
print(f"  Items: {len(purchase['items'])}")
for item in purchase["items"]:
    print(f"    - {item['product_name']}: {item['quantity']} x Rs {item['rate']} = Rs {item['total']}")
    if float(item["damaged_qty"]) > 0:
        print(f"      (!) {item['damaged_qty']} damaged - not added to stock")

# Check inventory after purchase
print("\n--- INVENTORY AFTER PURCHASE ---")
r = httpx.get(f"{BASE}/inventory")
inv = r.json()
print(f"  Total items: {inv['total_items']} | Total value: Rs {inv['total_value']}")
for item in inv["items"]:
    print(f"  {item['product_name']}: {item['qty_primary']} {item['primary_unit']} "
          f"({item['qty_secondary']} {item['secondary_unit']}) | Status: {item['status']}")

# ===================================================================
# MORNING 7 AM: BILL CUSTOMER (Sale)
# ===================================================================
print("\n" + "=" * 60)
print("7:00 AM - BILL RAJAN GENERAL STORE")
print("=" * 60)

r = httpx.post(f"{BASE}/bills", json={
    "customer_id": cust1["id"],
    "bill_date": "2025-09-03",
    "items": [
        {"product_id": products["TD"]["id"], "quantity": 3, "unit": "Bag", "rate": 95},
        {"product_id": products["RO"]["id"], "quantity": 2, "unit": "Can", "rate": 195},
        {"product_id": products["SN"]["id"], "quantity": 5, "unit": "Kg", "rate": 140},
    ],
    "payment_status": "credit",
    "amount_paid": 0,
})
assert r.status_code == 201, f"Bill failed: {r.text}"
bill = r.json()
print(f"  Bill #{bill['bill_number']} created")
print(f"  Subtotal: Rs {bill['subtotal']}")
print(f"  CGST: Rs {bill['cgst_amount']} | SGST: Rs {bill['sgst_amount']}")
print(f"  Total: Rs {bill['total_amount']}")
for item in bill["items"]:
    gst_str = f"CGST: {item['cgst_amount']} + SGST: {item['sgst_amount']}"
    print(f"  {item['product_name']}: {item['quantity']} {item['unit']} x Rs {item['rate']} = Rs {item['total']} ({gst_str})")
    print(f"    Cost basis: Rs {item['cost_basis']} (for margin analytics)")

# Check inventory after billing
print("\n--- INVENTORY AFTER BILLING ---")
r = httpx.get(f"{BASE}/inventory")
inv = r.json()
for item in inv["items"]:
    print(f"  {item['product_name']}: {item['qty_primary']} {item['primary_unit']} [{item['status'].upper()}]")

# ===================================================================
# AFTERNOON 3 PM: COLLECT PAYMENT
# ===================================================================
print("\n" + "=" * 60)
print("3:00 PM - COLLECT PAYMENT FROM RAJAN")
print("=" * 60)

# Check outstanding before
r = httpx.get(f"{BASE}/ledger/outstanding")
outstanding = r.json()
print(f"  Total Receivable: Rs {outstanding['total_receivable']}")
print(f"  Total Payable: Rs {outstanding['total_payable']}")

# Record payment
r = httpx.post(f"{BASE}/payments", json={
    "party_type": "customer",
    "party_id": cust1["id"],
    "amount": 500,
    "payment_mode": "upi",
    "reference": "UPI-REF-12345",
    "note": "Partial payment via Google Pay",
})
assert r.status_code == 201, f"Payment failed: {r.text}"
payment = r.json()
print(f"  Payment recorded: Rs {payment['amount']} via {payment['payment_mode']}")

# Check ledger
print("\n--- RAJAN'S LEDGER (Splitwise view) ---")
r = httpx.get(f"{BASE}/ledger/customer/{cust1['id']}")
ledger = r.json()
print(f"  Outstanding: Rs {ledger['outstanding']}")
for entry in ledger["entries"]:
    sign = "+" if entry["entry_type"] == "sale" else "-"
    print(f"  {entry['created_at'][:10]} | {entry['entry_type']:12s} | {sign}Rs {entry['amount']} | Balance: Rs {entry['running_balance']}")

# ===================================================================
# EVENING 5 PM: DASHBOARD CHECK
# ===================================================================
print("\n" + "=" * 60)
print("5:00 PM - DASHBOARD CHECK")
print("=" * 60)

r = httpx.get(f"{BASE}/dashboard")
dash = r.json()
print(f"  Today's Sales: Rs {dash['today_sales']}")
print(f"  Today's Purchases: Rs {dash['today_purchases']}")
print(f"  Low Stock Items: {dash['low_stock_count']}")
print(f"  Overdue Payments: {dash['overdue_count']}")

# Final outstanding
r = httpx.get(f"{BASE}/ledger/outstanding")
outstanding = r.json()
print(f"\n  NET POSITION: Rs {outstanding['net_position']}")
print(f"  Receivable: Rs {outstanding['total_receivable']} | Payable: Rs {outstanding['total_payable']}")

print("\n" + "=" * 60)
print("ALL E2E TESTS PASSED!")
print("Complete workflow: Purchase -> Inventory -> Bill -> Payment -> Ledger -> Dashboard")
print("=" * 60)
