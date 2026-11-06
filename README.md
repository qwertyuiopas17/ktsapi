# KTS API — Karma Tattva Samiksha

> **"Examining the truth behind every transaction."**

A production-grade backend API for Indian FMCG and Kirana distributors — replacing paper registers, bill stacks, and godown walks with OCR-powered purchase capture, real-time inventory tracking, GST-compliant billing, and Splitwise-style party ledgers.

---

## The Problem

Indian distributors run their entire business on paper. A typical day looks like this:

- **Morning:** Supplier trucks arrive. The shop owner (Raju) counts bags, checks for damage, and files the printed invoice in a cloth bag. He has no idea what his current stock is without physically walking to the godown.
- **Afternoon:** Customers arrive. Raju writes bills by hand, manually calculating GST. He checks a notebook to see if a customer has unpaid credit. Mistakes happen daily.
- **Evening:** Raju tries to figure out who owes him money, what stock is running low, and whether he made a profit. The answers are buried across 5 different registers.

**KTS solves this** by digitizing the entire flow: scan a supplier invoice with your phone camera, and inventory updates automatically. Bill a customer in under 30 seconds with auto-GST. Know exactly who owes you money and what stock you have — without leaving the counter.

---

## The Solution — What KTS Does

### 1. OCR Purchase Capture (The Front Door)
Scan a printed supplier invoice with your phone camera. KTS reads it using AI (Groq Vision API), extracts the line items, matches products and suppliers against your database, and creates the purchase record. Stock updates automatically. No manual data entry.

### 2. Real-Time Inventory
Every purchase adds stock. Every bill deducts stock. Every return re-adds stock. Wastage and adjustments are tracked. You always know your exact stock — in both units (e.g., "5 Bags = 250 Kg"). Low-stock alerts tell you what to reorder before you run out.

### 3. GST-Compliant Billing
Create invoices in under 30 seconds. GST is auto-calculated from HSN codes — CGST+SGST for intra-state, IGST for inter-state. Supports 3 price tiers (retail, wholesale, special) per product. Credit limit enforcement prevents over-extending to risky customers.

### 4. Party Ledger (Who Owes What)
Every sale, purchase, payment, and return is tracked in a Splitwise-style ledger for each customer and supplier. Outstanding balances update in real-time. One-tap WhatsApp payment reminders.

### 5. Bill Sharing
Generate professional PDF invoices (A4 for formal, 80mm thermal for receipt printers) and share via WhatsApp with a single tap.

### 6. Expense Tracking
Log business expenses (fuel, rent, salary, transport, etc.) with category-wise P&L summaries. Receipt photo upload support.

---

## Architecture

```
                    +---------------------+
                    |   React Native App  |    (Not yet built — Phase 2)
                    |   (Expo / TypeScript)|
                    +----------+----------+
                               |
                          HTTPS / JWT
                               |
                    +----------v----------+
                    |     KTS API         |
                    |     (FastAPI)       |
                    +----------+----------+
                               |
              +----------------+----------------+
              |                |                |
     +--------v------+  +-----v------+  +------v-------+
     |  PostgreSQL   |  | Groq Vision|  |  AWS S3      |
     |  (Supabase /  |  | API (OCR)  |  |  (Bill       |
     |   Railway)    |  |            |  |   Images)    |
     +---------------+  +------------+  +--------------+
```

### Tech Stack

| Layer | Technology |
|:------|:-----------|
| Framework | FastAPI (Python 3.11+) |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Auth | PyJWT (HS256) + Firebase Phone Auth (planned) |
| OCR | Groq Vision API (llama-4-scout) + PyMuPDF |
| PDF | ReportLab |
| Rate Limiting | slowapi (installed, not yet wired) |

---

## Current Status

### What is Built (Sprint 1 + Sprint 2 — Complete)

**Database Layer — 15 tables, fully modeled:**

| Model | Purpose |
|:------|:--------|
| Business | Multi-tenant root (name, GSTIN, state, bill prefix) |
| User | Phone auth, Firebase UID, PIN, role |
| Product | Name, shortcode, HSN, GST rate, units, conversion factor, 3 sell prices, low-stock threshold |
| Customer | Name, phone, address, state, GSTIN, credit limit, outstanding, price tier |
| Company | Supplier — name, GSTIN, state, contact, outstanding |
| Inventory | Per-product stock (primary + secondary units) |
| InventoryTxn | Audit trail — every stock movement with type, qty, timestamp, reference |
| Purchase | Inbound goods — invoice number, date, totals, payment status, OCR source/confidence |
| PurchaseItem | Line items with discount, damaged qty, cost basis |
| Bill | Outbound invoice — bill number, type, GST breakdown, payment status |
| BillItem | Line items with cost basis at time of sale |
| Payment | Cash/UPI/bank payments for customers and suppliers |
| LedgerEntry | Double-entry audit trail with running balances |
| Expense | Business expenses with 9 categories |

**API Endpoints — 35+ built and tested:**

| Group | Endpoints | Key Features |
|:------|:----------|:-------------|
| Auth | 2 | Phone OTP send/verify, JWT token generation |
| Products | 6 | CRUD + search + HSN auto-lookup + auto inventory init |
| Customers | 5 | CRUD + search by name/phone |
| Companies | 5 | CRUD + search by name/GSTIN |
| Purchases | 3 | Create (auto stock-in + wastage + ledger), list, OCR scan |
| Bills | 4 | Create (auto GST + stock-out + credit check + ledger), list, PDF, WhatsApp share |
| Payments | 1 | Record payment (auto ledger + outstanding update) |
| Ledger | 2 | Party transaction history, outstanding summary |
| Inventory | 1 | Live stock levels with low-stock filtering |
| Dashboard | 1 | Today's sales, purchases, expenses, low stock count, overdue count |
| Expenses | 5 | CRUD + category-wise P&L summary |

**Business Logic Services — 6 built:**

| Service | What It Does |
|:--------|:-------------|
| `gst_engine.py` | GST calculation: 5 slabs (0/5/12/18/28%) x intra/inter-state = auto CGST+SGST or IGST |
| `inventory_service.py` | Stock in/out/wastage/adjustment with InventoryTxn audit trail |
| `auth_service.py` | JWT creation + validation, `get_current_user` dependency |
| `ocr_service.py` | Groq Vision OCR, PDF-to-image, rotating API keys, structured extraction |
| `bill_pdf.py` | PDF invoice generation (A4 formal + 80mm thermal receipt) |
| `unit_converter.py` | Primary-to-secondary unit conversion (Bag to Kg, Can to L, etc.) |

**Testing — 2 suites, all passing:**

| Suite | Tests | Coverage |
|:------|:------|:---------|
| `test_e2e.py` | ~11 | Full flow: Product > Customer > Company > Purchase > Inventory > Bill > Payment > Ledger > Dashboard |
| `test_improvements.py` | 15 | JWT auth, OCR endpoint, Bill PDF (A4+thermal), WhatsApp share, Expense CRUD, category summary |

---

### What is NOT Built Yet

#### Backend Remaining (~7 working days)

| # | Task | Priority | Why |
|:--|:-----|:---------|:----|
| 1 | Wire JWT auth to all endpoints | P0 | All routes currently open — auth service built but not plugged in |
| 2 | Firebase real phone auth | P0 | OTP verification is stubbed (always succeeds) |
| 3 | Multi-tenancy | P0 | Hardcoded BUSINESS_ID — must extract from JWT |
| 4 | Bill return / credit note | P1 | Stock re-add + ledger reversal on customer returns |
| 5 | Delivery challan | P2 | Goods movement without tax invoice, convert to invoice later |
| 6 | OCR confidence gating | P1 | 4-state validation: confirming / needs-fix / auto-committed / failed |
| 7 | Per-supplier OCR template learning | P2 | Auto-commit after 50 clean scans from same supplier |
| 8 | S3 image upload | P1 | Bill images processed but not persisted |
| 9 | Google Document AI fallback | P2 | Production OCR fallback for low-confidence Groq results |
| 10 | Payment reminder scheduler | P2 | WhatsApp reminders for overdue payments |
| 11 | Bulk product import (CSV/Excel) | P2 | Mass product onboarding |
| 12 | Global search | P2 | Unified search across all entities |
| 13 | Stock adjustment endpoint | P1 | Physical count reconciliation (service exists, endpoint does not) |
| 14 | Rate limiting | P1 | slowapi installed but not configured |
| 15 | Recurring expenses | P3 | Template-based recurring expense reminders |
| 16 | Deployment | P1 | Dockerfile, CI/CD, hosting config |

#### Frontend (~10-12 weeks)

The React Native mobile app (Expo + TypeScript) is **not started**. A complete [Frontend Design Specification](FRONTEND_DESIGN_SPEC.md) has been written covering color system, typography, component library, wireframes for 9 screens, interaction patterns, and tech stack.

---

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL (production) or SQLite (development — works out of the box)

### Setup

```bash
# Clone
git clone https://github.com/qwertyuiopas17/ktsapi.git
cd ktsapi

# Virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env         # Windows
cp .env.example .env           # Linux/Mac
# Edit .env with your settings (JWT secret, database URL, API keys)

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Open API docs
# http://localhost:8000/docs
```

### Run Tests

```bash
# Sprint 1 — full E2E flow
pytest test_e2e.py -v

# Sprint 2 — auth, OCR, PDF, expenses
pytest test_improvements.py -v

# Quick smoke test
pytest test_smoke.py -v
```

---

## API Reference

### Authentication
```
POST /api/v1/auth/send-otp          Send OTP to phone number
POST /api/v1/auth/verify-otp        Verify OTP, receive JWT token
```

### Products
```
POST   /api/v1/products             Create product (auto-init inventory)
GET    /api/v1/products             List products (paginated)
GET    /api/v1/products/search?q=   Search by name or shortcode
GET    /api/v1/products/{id}        Get product detail
PUT    /api/v1/products/{id}        Update product
DELETE /api/v1/products/{id}        Soft deactivate
```

### Customers
```
POST   /api/v1/customers            Create customer
GET    /api/v1/customers             List customers
GET    /api/v1/customers/search?q=   Search by name or phone
GET    /api/v1/customers/{id}        Get detail
PUT    /api/v1/customers/{id}        Update
```

### Companies (Suppliers)
```
POST   /api/v1/companies            Create supplier
GET    /api/v1/companies             List suppliers
GET    /api/v1/companies/search?q=   Search by name or GSTIN
GET    /api/v1/companies/{id}        Get detail
PUT    /api/v1/companies/{id}        Update
```

### Purchases + OCR
```
POST   /api/v1/purchases            Create purchase (auto stock-in, wastage, ledger)
GET    /api/v1/purchases             List purchases
POST   /api/v1/purchases/scan       Upload invoice image for OCR extraction
```

### Bills
```
POST   /api/v1/bills                Create bill (auto GST, stock-out, credit check, ledger)
GET    /api/v1/bills                 List bills
GET    /api/v1/bills/{id}/pdf       Download PDF invoice (?format=a4|thermal)
GET    /api/v1/bills/{id}/share/whatsapp   Get WhatsApp share link
```

### Payments & Ledger
```
POST   /api/v1/payments             Record payment (auto ledger + outstanding update)
GET    /api/v1/ledger/{type}/{id}   Party transaction history with running balance
GET    /api/v1/outstanding           Receivable + payable + net summary
```

### Inventory
```
GET    /api/v1/inventory             Stock levels (filter: ?low_stock=true)
```

### Dashboard
```
GET    /api/v1/dashboard             Today's sales, purchases, expenses, alerts
```

### Expenses
```
POST   /api/v1/expenses             Create expense
GET    /api/v1/expenses              List (filter: ?category=&from_date=&to_date=)
GET    /api/v1/expenses/{id}         Get detail
DELETE /api/v1/expenses/{id}         Delete
GET    /api/v1/expenses/summary     Category-wise P&L breakdown
```

---

## Project Structure

```
kts-api/
|
|-- app/
|   |-- main.py                    FastAPI app + CORS + router registration
|   |-- config.py                  Pydantic Settings (JWT, Firebase, S3, DB)
|   |-- database.py                SQLAlchemy engine + session factory
|   |
|   |-- models/
|   |   |-- models.py              15 database tables (all UUIDs, timestamped)
|   |
|   |-- schemas/
|   |   |-- auth.py                OTP, token request/response schemas
|   |   |-- entities.py            Product, Customer, Company schemas
|   |   |-- transactions.py        Purchase, Bill, Payment, Expense, Ledger schemas
|   |
|   |-- services/
|   |   |-- auth_service.py        JWT auth (create/decode token, get_current_user)
|   |   |-- gst_engine.py          GST calculation (5 slabs x intra/inter-state)
|   |   |-- inventory_service.py   Stock in/out/wastage/adjustment + audit trail
|   |   |-- ocr_service.py         Groq Vision OCR + PDF-to-image + product matching
|   |   |-- bill_pdf.py            ReportLab PDF generator (A4 + 80mm thermal)
|   |
|   |-- routers/
|   |   |-- auth.py                Phone OTP + JWT endpoints
|   |   |-- products.py            Product CRUD + search
|   |   |-- parties.py             Customer + Company CRUD + search
|   |   |-- purchases.py           Purchase creation + OCR scan
|   |   |-- bills.py               Bill creation + PDF + WhatsApp share
|   |   |-- expenses.py            Expense CRUD + category summary
|   |   |-- dashboard.py           Payments, ledger, inventory, dashboard
|   |
|   |-- utils/
|       |-- unit_converter.py      Bag/Can/Case to Kg/L/Piece conversion
|
|-- alembic/                       Database migrations
|-- test_smoke.py                  Quick health checks
|-- test_e2e.py                    Sprint 1 full-flow E2E tests
|-- test_improvements.py           Sprint 2 feature tests (15 tests)
|-- requirements.txt               Python dependencies
|-- .env.example                   Environment variable template
|-- REMAINING_TASKS.md             Detailed breakdown of all remaining work
|-- FRONTEND_DESIGN_SPEC.md        Complete mobile app design specification
```

---

## Transactional Integrity

Every stock-affecting operation is atomic. When a purchase is created:

1. Purchase record saved
2. For each item: `(quantity - damaged_qty)` added to inventory
3. InventoryTxn audit record created (type: `purchase_in`)
4. If damaged_qty > 0: separate InventoryTxn (type: `wastage`)
5. Product's latest purchase_price updated
6. Company ledger entry created (if credit)
7. Company outstanding balance updated

If any step fails, the entire transaction rolls back. Same pattern for bills (stock-out + ledger) and payments (outstanding update + ledger).

---

## GST Engine

Handles all Indian GST scenarios:

| Scenario | Tax Applied |
|:---------|:------------|
| Same state (intra-state) | CGST (half rate) + SGST (half rate) |
| Different state (inter-state) | IGST (full rate) |

Supported slabs: **0%, 5%, 12%, 18%, 28%**

GST rate is auto-determined from the product's HSN code. The engine is invoked automatically during bill creation — the user never manually calculates tax.

---

## Future Roadmap

### Phase 2 — Post-MVP
- Offline mode (WatermelonDB + SQLite + CRDT sync)
- P&L analytics dashboard (using captured cost_basis data)
- Bluetooth thermal printing
- Multi-user support (owner + helpers with role-based access)
- Beat planning (daily delivery route optimization)
- Barcode scanning for quick billing
- GSTR-1 export (auto-generate GST return data)
- Bank statement reconciliation
- Supplier auto-ordering (predict reorder from consumption velocity)
- Hindi/Punjabi language support

---

## Environment Variables

```env
# Database
DATABASE_URL=sqlite:///./kts_dev.db    # Dev (SQLite, works out of the box)
# DATABASE_URL=postgresql://user:pass@host:5432/kts_db   # Production

# JWT
JWT_SECRET=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Firebase (for real phone auth — currently stubbed)
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json

# OCR (Groq Vision API)
GROQ_API_KEYS=key1,key2,key3

# S3 (for bill image storage — not yet implemented)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
AWS_REGION=ap-south-1
```

---

## Contributing

This is a solo project in active development. If you want to contribute:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/returns`)
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

Priority areas for contribution:
- Wiring JWT auth to all endpoints (P0)
- Bill return/credit note endpoint (P1)
- Stock adjustment endpoint (P1)
- Frontend React Native app (massive scope)

---

## License

MIT

---

**Built by [@qwertyuiopas17](https://github.com/qwertyuiopas17)**
