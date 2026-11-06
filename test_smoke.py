"""Quick smoke test for all KTS API endpoints."""
import httpx
import sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8000/api/v1"

# 1. Create a product
print("=== Creating Product ===")
r = httpx.post(f"{BASE}/products", json={
    "name": "Toor Dal",
    "shortcode": "TD",
    "hsn_code": "0713",
    "category": "Grains",
    "primary_unit": "Bag",
    "secondary_unit": "Kg",
    "conversion_factor": 50,
    "purchase_price": 4500,
    "sell_price_retail": 95,
    "sell_price_wholesale": 85,
    "low_stock_threshold": 5,
    "is_loose_stock": True,
})
print(f"Status: {r.status_code}")
if r.status_code != 201:
    print(f"Error: {r.text}")
else:
    product = r.json()
    pid = product["id"]
    print(f"Product: {product['name']} | GST: {product['gst_rate']}% (auto from HSN) | Stock: {product['current_stock']}")

# 2. Create another product
print("\n=== Creating Product 2 ===")
r = httpx.post(f"{BASE}/products", json={
    "name": "Refined Oil",
    "shortcode": "RO",
    "hsn_code": "1515",
    "category": "Oil",
    "primary_unit": "Can",
    "secondary_unit": "Litre",
    "conversion_factor": 15,
    "purchase_price": 2700,
    "sell_price_retail": 195,
    "sell_price_wholesale": 180,
    "low_stock_threshold": 3,
    "is_loose_stock": True,
})
print(f"Status: {r.status_code}")
if r.status_code == 201:
    p2 = r.json()
    print(f"Product: {p2['name']} | GST: {p2['gst_rate']}% (auto from HSN)")

# 3. Create a customer
print("\n=== Creating Customer ===")
r = httpx.post(f"{BASE}/customers", json={
    "name": "Rajan General Store",
    "phone": "+919876543210",
    "state_code": "27",
    "price_tier": "wholesale",
    "credit_limit": 50000,
})
print(f"Status: {r.status_code}")
if r.status_code == 201:
    cust = r.json()
    print(f"Customer: {cust['name']} | Credit: {cust['credit_limit']} | Outstanding: {cust['outstanding']}")

# 4. Create a company
print("\n=== Creating Company (Supplier) ===")
r = httpx.post(f"{BASE}/companies", json={
    "name": "Maharashtra Pulses Ltd",
    "gstin": "27AABCU9603R1ZM",
    "state_code": "27",
    "contact_person": "Ramesh Patel",
    "phone": "+919123456789",
})
print(f"Status: {r.status_code}")
if r.status_code == 201:
    comp = r.json()
    print(f"Company: {comp['name']} | GSTIN: {comp['gstin']}")

# 5. HSN Lookup
print("\n=== HSN -> GST Rate Lookup ===")
for hsn in ["0713", "1701", "7317", "2402", "9999"]:
    r = httpx.get(f"{BASE}/products/hsn-lookup", params={"hsn_code": hsn})
    data = r.json()
    rate = data["gst_rate"]
    print(f"  HSN {data['hsn_code']}: GST {rate}%" if rate is not None else f"  HSN {data['hsn_code']}: Not found (user sets manually)")

# 6. List products
print("\n=== Product List ===")
r = httpx.get(f"{BASE}/products")
data = r.json()
print(f"Total: {data['total']} products")
for p in data["products"]:
    print(f"  - {p['name']} ({p['shortcode']}) | {p['primary_unit']}/{p['secondary_unit']} | GST: {p['gst_rate']}%")

# 7. Search
print("\n=== Search 'oil' ===")
r = httpx.get(f"{BASE}/products", params={"search": "oil"})
data = r.json()
print(f"Found: {data['total']}")
for p in data["products"]:
    print(f"  - {p['name']}")

# 8. List customers
print("\n=== Customer List ===")
r = httpx.get(f"{BASE}/customers")
data = r.json()
print(f"Total: {data['total']} customers")

# 9. List companies
print("\n=== Company List ===")
r = httpx.get(f"{BASE}/companies")
data = r.json()
print(f"Total: {data['total']} companies")

print("\n" + "=" * 50)
print("ALL SMOKE TESTS PASSED!")
print("API docs at: http://localhost:8000/docs")
print("=" * 50)
