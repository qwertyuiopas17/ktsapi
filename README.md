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

**Phase 1 (secure and correct foundation) — implemented.** See
[`docs/kts-implementation-plan.md`](docs/kts-implementation-plan.md) for the
full 4-phase plan and [`docs/kts-kolkata-gtm.md`](docs/kts-kolkata-gtm.md) for
the go-to-market plan.

| Area | What Phase 1 delivers |
|:--|:--|
| Auth | Firebase Phone Auth ID token → `POST /auth/firebase` → 60-min access JWT + 30-day rotating refresh token (reuse detection), `token_version` revocation, logout / logout-all, bcrypt PIN unlock with lockout |
| Tenancy | No hardcoded business id. Every route takes a `RequestContext`; every lookup is scoped by `business_id` (`get_owned` returns 404 across tenants) |
| Roles | owner / accountant / manager / delivery / warehouse matrix (`app/deps.py`); staff are invited by the owner (`/api/v1/users`) |
| Invoices | Per-business, per-FY, gap-free series `INV/2627/00042` (row-locked); separate series for challans; round-off to the rupee; bills are cancelled (stock + ledger reversed), never deleted |
| GST | Effective-dated HSN rate table (`data/hsn_rates.json`) with GST 2.0 rates from 22 Sep 2025 (soap, hair oil, shampoo, toothpaste → 5%) |
| Stock & cost | `SELECT … FOR UPDATE` on inventory, explicit txn types, moving-average landed cost (`Inventory.avg_cost`), `BillItem.cost_basis` per billed unit, damaged goods written off as wastage, batch stock counts / opening stock |
| Platform | Alembic is the only schema source, pytest suite on Postgres in CI, ruff, Dockerfile + docker-compose, rate limiting, JSON logs, Sentry hook, [operations runbook](docs/operations.md) |

Still open from Phase 1 (need accounts/infrastructure rather than code):
staging deployment in Mumbai, Sentry project, S3 presigned uploads, first
backup restore drill, CA confirmation of tobacco/pan-masala cess.

---

## Quick Start

### With Docker (Postgres + Redis)

```bash
cp .env.example .env            # keep AUTH_DEV_STUB=true for local work
docker compose up --build       # runs `alembic upgrade head`, then the API on :8000
```

### Without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # set DATABASE_URL (SQLite works for quick local runs)
alembic upgrade head
uvicorn app.main:app --reload
# http://localhost:8000/docs
```

Local sign-in without Firebase (development only, `AUTH_DEV_STUB=true`):

```bash
curl -X POST localhost:8000/api/v1/auth/firebase -H 'content-type: application/json' \
     -d '{"id_token": "dev:+919876543210"}'
```

### Run Tests

```bash
pytest                                   # SQLite, quick
TEST_DATABASE_URL=postgresql://kts:kts@localhost:5432/kts_test pytest   # what CI runs
ruff check .
```

The concurrency tests (last-unit race, 50 parallel bills) only run on Postgres.

### CI and Render staging

GitHub Actions runs Ruff, the full test suite against PostgreSQL 16, and a Docker
build for every pull request and push to `main`. Render waits for those checks
before auto-deploying `main`; its pre-deploy command runs `alembic upgrade head`.

1. In Render, create a Blueprint from this repository's `render.yaml`.
2. Enter `CORS_ORIGINS` as a JSON array and provide the Firebase project ID.
3. Add the Firebase service-account JSON as a Render **Secret File** at
   `/etc/secrets/firebase-credentials.json`.
4. Confirm `GET /health` succeeds after the first deploy. Add Sentry, S3, and
   Groq secrets later as those integrations become available.

The blueprint is a paid staging baseline (`starter` web service and
`basic-256mb` Postgres) to avoid ephemeral free-tier infrastructure. It uses
Singapore because Render does not currently offer Mumbai. If customer data must
remain in India, deploy the same Docker image and release command with an
India-region provider instead. `RATE_LIMIT_STORAGE_URI=memory://` is suitable
only while staging runs one web-service instance; configure managed Redis before
scaling horizontally.

---

## API Reference

All routes except auth sign-in/refresh and health need `Authorization: Bearer <access_token>`.

### Authentication & users
```
POST /api/v1/auth/firebase          Firebase phone ID token -> access + refresh tokens
POST /api/v1/auth/refresh           Rotate refresh token
POST /api/v1/auth/logout            Revoke this device's refresh token
POST /api/v1/auth/logout-all        Revoke every session of the user
GET  /api/v1/auth/me                Current user and business
POST /api/v1/auth/set-pin           Set quick-unlock PIN
POST /api/v1/auth/verify-pin        Check PIN (locks out after 5 wrong tries)
PUT  /api/v1/auth/business          Business profile, invoice prefix, credit policy (owner)
GET|POST /api/v1/users, PATCH /api/v1/users/{id}   Staff and roles (owner)
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
GET    /api/v1/bills/{id}           Bill detail
POST   /api/v1/bills/{id}/cancel    Cancel (reverses stock + ledger; number stays used)
GET    /api/v1/bills/{id}/pdf       Download PDF invoice (?format=a4|thermal)
GET    /api/v1/bills/{id}/share/whatsapp   Get WhatsApp share link
```

### Payments & Ledger
```
POST   /api/v1/payments             Record payment (auto ledger + outstanding update)
GET    /api/v1/ledger/{type}/{id}   Party transaction history with running balance
GET    /api/v1/ledger/outstanding    Receivable + payable + net summary
```

### Inventory
```
GET    /api/v1/inventory             Stock levels at moving-average cost (?low_stock_only=true)
GET    /api/v1/inventory/{id}/movements   Stock movement history
POST   /api/v1/inventory/adjustments      Batch stock count / opening stock (owner, warehouse)
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
|   |-- deps.py                    RequestContext + role checks (allow(...))
|   |-- rate_limit.py              slowapi limiter (per user / per IP)
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
|   |   |-- auth_service.py        Access/refresh tokens, PIN hashing, Firebase verification
|   |   |-- numbering.py           Financial-year invoice series (row-locked)
|   |   |-- gst_engine.py          GST calculation, round-off, effective-dated HSN lookup
|   |   |-- inventory_service.py   Stock in/out/wastage/adjustment + audit trail
|   |   |-- ocr_service.py         Groq Vision OCR + PDF-to-image + product matching
|   |   |-- bill_pdf.py            ReportLab PDF generator (A4 + 80mm thermal)
|   |
|   |-- routers/
|   |   |-- auth.py                Firebase phone sign-in, refresh, PIN, business setup
|   |   |-- users.py               Staff invites and roles (owner)
|   |   |-- products.py            Product CRUD + search
|   |   |-- parties.py             Customer + Company CRUD + search
|   |   |-- purchases.py           Purchase creation + OCR scan
|   |   |-- bills.py               Bill creation + PDF + WhatsApp share
|   |   |-- expenses.py            Expense CRUD + category summary
|   |   |-- dashboard.py           Payments, ledger, inventory, dashboard
|   |
|   |-- utils/
|       |-- unit_converter.py      Bag/Can/Case to Kg/L/Piece conversion
|       |-- scoping.py             get_owned(): tenant-scoped lookup, 404 across tenants
|
|-- alembic/                       Database migrations (the only source of the schema)
|-- tests/                         pytest suite (auth, tenancy, roles, billing, GST, migrations, concurrency)
|-- data/hsn_rates.json            Effective-dated HSN -> GST rates
|-- docs/                          Plans and operations runbook
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
