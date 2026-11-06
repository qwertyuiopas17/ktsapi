# KTS — Remaining Tasks (Detailed)

> **Last updated:** 2026-09-04
> **Status:** Sprint 1 ✅ + Sprint 2 ✅ complete. Everything below is TODO.

---

## What's Already Done

| Area | Status | Details |
|:---|:---|:---|
| Project scaffolding | ✅ | FastAPI + SQLAlchemy + Alembic + venv |
| Database models | ✅ | 15 tables (Business, User, Product, Customer, Company, Inventory, InventoryTxn, Purchase, PurchaseItem, Bill, BillItem, Payment, LedgerEntry, Expense) |
| Config & env | ✅ | Pydantic Settings, .env file, JWT/Firebase/S3/DocAI config slots |
| Auth (stub) | ✅ | Phone OTP send/verify (mock Firebase), JWT token generation |
| JWT auth service | ✅ | Real `get_current_user` / `get_optional_user` dependencies (from Aethel pattern) |
| Product CRUD | ✅ | Create, list, search, get, update, deactivate + auto inventory init |
| Customer CRUD | ✅ | Create, list, search, get, update |
| Company CRUD | ✅ | Create, list, search, get, update |
| GST engine | ✅ | 4 slabs (0/5/12/18/28%) × intra/inter-state (CGST+SGST vs IGST) |
| Inventory service | ✅ | stock_in, stock_out, wastage, adjustment + audit trail (InventoryTxn) |
| Purchase endpoints | ✅ | Create (auto stock-in, wastage tracking, company ledger) |
| Bill creation | ✅ | Auto-GST, auto stock deduction, credit limit check, cost_basis capture |
| Payment endpoints | ✅ | Customer & company payments with auto ledger + outstanding update |
| Ledger endpoints | ✅ | Party ledger view, outstanding summary |
| Dashboard | ✅ | Today's sales/purchases/expenses, low stock count, overdue count |
| OCR scan endpoint | ✅ | `POST /purchases/scan` — Groq Vision API + PDF→image pipeline |
| Bill PDF | ✅ | A4 + thermal (80mm) format with reportlab |
| WhatsApp share | ✅ | Pre-formatted message + wa.me deep link |
| Expense CRUD | ✅ | Create, list, get, delete + category summary (P&L) |
| DB safety | ✅ | expire_on_commit, check_same_thread, postgres:// normalization, UTF-8 fix |

**Total endpoints built: 30+**

---

## BACKEND REMAINING

### 1. Wire JWT Auth to All Endpoints
**Priority: P0 | Effort: 2-3 hours**

Currently all endpoints are open (no auth required). Need to add `Depends(get_current_user)` to every router.

```python
# What needs to change in EVERY router:
from app.services.auth_service import get_current_user

@router.post("")
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # ← ADD THIS
):
    # Replace hardcoded BUSINESS_ID with:
    business_id = current_user["business_id"]
```

**Files to modify:**
- `app/routers/products.py` — replace `BUSINESS_ID` with `current_user["business_id"]`
- `app/routers/parties.py` — same
- `app/routers/purchases.py` — same
- `app/routers/bills.py` — same
- `app/routers/expenses.py` — same
- `app/routers/dashboard.py` — same (all 4 sub-routers)

**Also need:**
- Auth-gated middleware (reject all `/api/v1/*` without Bearer token)
- `get_optional_user` for health/docs endpoints

---

### 2. Firebase Real Auth Integration
**Priority: P0 | Effort: 4-6 hours**

Replace the stub OTP flow with real Firebase Admin SDK.

**Tasks:**
- [ ] Install `firebase-admin` Python SDK
- [ ] Create Firebase project + enable phone auth
- [ ] Download `firebase-credentials.json` → configure in `.env`
- [ ] `app/services/firebase_service.py`:
  - `verify_id_token(token)` — validate Firebase ID token
  - `get_or_create_user(firebase_uid, phone)` — upsert KTS user from Firebase
- [ ] Update `app/routers/auth.py`:
  - `POST /auth/firebase-login` — accept Firebase ID token → return KTS JWT
  - Remove stub OTP endpoints (or keep as fallback for dev)
- [ ] PIN setup endpoint (`POST /auth/set-pin`)
- [ ] PIN verify endpoint (`POST /auth/verify-pin`)

---

### 3. Multi-Tenancy (Per-Business Data Isolation)
**Priority: P0 | Effort: 3-4 hours**

Currently hardcoded: `BUSINESS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")`

**Tasks:**
- [ ] Remove `BUSINESS_ID` constant from all routers
- [ ] Extract `business_id` from JWT token (already in the payload)
- [ ] Add `business_id` filter to ALL queries (already present in most, just using wrong source)
- [ ] Business onboarding endpoint:
  - `POST /api/v1/business/setup` — create business profile after first login
  - Fields: name, gstin, address, state_code, phone, bill_prefix
- [ ] Ensure no cross-tenant data leakage (every query must include `business_id` filter)

---

### 4. Bill Return / Credit Note
**Priority: P1 | Effort: 4-5 hours**

From PRD §4 F3.4 — customers return items.

**Tasks:**
- [ ] Schema: `ReturnCreate` (original_bill_id, items[{bill_item_id, return_qty, reason}])
- [ ] Schema: `ReturnResponse`
- [ ] Model: Add `bill_type` values: `credit_note`, link `original_bill_id`
- [ ] Endpoint: `POST /api/v1/bills/{bill_id}/return`
- [ ] On save (TRANSACTIONAL):
  - Create credit note (bill_type = 'credit_note', linked to original bill)
  - Stock re-added to inventory (`inventory_txn: 'return_in'`)
  - Customer outstanding reduced
  - Ledger entry created (type: 'return')
- [ ] Validation: return qty ≤ original qty for each item
- [ ] Partial returns supported (return 2 of 5 bags)

---

### 5. Delivery Challan
**Priority: P2 | Effort: 3-4 hours**

From PRD §4 F3.5 — goods move without tax invoice.

**Tasks:**
- [ ] `POST /api/v1/challans` — same as bill but `bill_type = 'challan'`
- [ ] Stock moves out (inventory_txn: 'sale_out') but NO GST calculated
- [ ] No ledger entry (not a financial transaction until converted)
- [ ] `POST /api/v1/challans/{id}/convert` — convert challan to invoice
  - Creates a new bill linked to the challan
  - GST calculated on conversion
  - Ledger entry created
  - Challan marked as converted

---

### 6. OCR Confidence Gating & Auto-Validation
**Priority: P1 | Effort: 6-8 hours**

The current OCR just returns raw extracted data. Need the 4-state confidence system from PRD §4 F1.1a.

**Tasks:**
- [ ] `app/services/ocr_validator.py`:
  - Per-line check: `total == qty × rate - discount`
  - Invoice-level: `Σ line totals + GST == printed invoice total`
  - Historical sanity: `qty/rate within ±3σ of past purchases for this supplier+product`
  - Output: per-field confidence score + overall bill confidence
- [ ] Confidence states:
  - `confirming` — high confidence + totals reconcile → one-tap confirm
  - `needs_fix` — low confidence or failed validation → highlight suspect fields
  - `auto_committed` — trusted supplier + bill reconciles → auto-create purchase
  - `failed` — unreadable → fall through to manual entry
- [ ] `POST /api/v1/purchases/ocr-confirm` — confirm OCR draft with optional corrections
- [ ] Store corrections for template learning

---

### 7. Per-Supplier OCR Template Learning
**Priority: P2 | Effort: 4-6 hours**

After N successful scans from the same supplier, learn their invoice layout.

**Tasks:**
- [ ] Model: `OcrTemplate` table (supplier_id, field_positions JSON, sample_count, trust_score)
- [ ] Track consecutive clean scans per supplier
- [ ] After 50 clean scans → graduate to auto-commit
- [ ] Any reconciliation failure → drop back to verify-first
- [ ] `POST /api/v1/purchases/ocr-feedback` — log corrections → update template
- [ ] Template matching: when scanning a new invoice, check if supplier has a template → apply field positions as hints

---

### 8. S3 Image Upload Service
**Priority: P1 | Effort: 2-3 hours**

Bill images need to be stored, not just processed.

**Tasks:**
- [ ] Install `boto3`
- [ ] `app/services/s3_service.py`:
  - `upload_image(file_bytes, filename, folder)` → S3 URL
  - `generate_presigned_url(key)` → temporary download URL
  - `delete_image(key)`
- [ ] `POST /api/v1/uploads/presigned-url` — generate upload URL for mobile app
- [ ] Store `ocr_image_url` on purchases after upload
- [ ] Store `receipt_url` on expenses after upload
- [ ] Configure S3 bucket CORS for direct mobile uploads

---

### 9. Google Document AI Fallback
**Priority: P2 | Effort: 4-5 hours**

Current OCR uses Groq Vision (free but less accurate). Need Google Document AI as production fallback.

**Tasks:**
- [ ] Install `google-cloud-documentai`
- [ ] `app/services/docai_service.py`:
  - Create Document AI processor (Invoice Parser)
  - `process_invoice(image_bytes)` → structured data
  - Map Document AI fields to KTS purchase schema
- [ ] OCR service fallback chain: Groq Vision → Document AI (if Groq fails or confidence < 0.6)
- [ ] Cost tracking (Document AI charges per page)

---

### 10. Payment Reminder Scheduler
**Priority: P2 | Effort: 3-4 hours**

From PRD §4 F4.3 — WhatsApp reminders for overdue payments.

**Tasks:**
- [ ] `app/services/reminder_service.py`:
  - Query customers with outstanding > 0 and last_payment > X days
  - Generate reminder message
  - Return WhatsApp links for batch sending
- [ ] `GET /api/v1/reminders/overdue` — list customers needing reminders
- [ ] `POST /api/v1/reminders/send` — mark reminders as sent (tracking)
- [ ] Aging buckets: 0-30d (green), 30-60d (yellow), 60-90d (orange), 90+d (red)
- [ ] Optional: background cron job (APScheduler) for auto-reminders

---

### 11. Bulk Product Import (CSV/Excel)
**Priority: P2 | Effort: 3-4 hours**

**Tasks:**
- [ ] Install `openpyxl` (Excel) or use CSV stdlib
- [ ] `POST /api/v1/products/import` — accept CSV/Excel file
- [ ] Template download: `GET /api/v1/products/import/template`
- [ ] Validation: check for duplicates (by shortcode/name), validate HSN codes
- [ ] Return import summary: {created: N, skipped: N, errors: [...]}
- [ ] Auto-create inventory rows for new products

---

### 12. Global Search Endpoint
**Priority: P2 | Effort: 2-3 hours**

**Tasks:**
- [ ] `GET /api/v1/search?q=...` — unified search across:
  - Products (name, shortcode, HSN)
  - Customers (name, phone)
  - Companies (name, GSTIN)
  - Bills (bill_number)
  - Purchases (invoice_number)
- [ ] Return categorized results: `{products: [...], customers: [...], ...}`
- [ ] Limit results per category (top 5 each)

---

### 13. Stock Adjustment Endpoint
**Priority: P1 | Effort: 2-3 hours**

Physical count reconciliation — already have the service, need the endpoint.

**Tasks:**
- [ ] Schema: `StockAdjustCreate` (product_id, actual_qty, reason)
- [ ] Endpoint: `POST /api/v1/inventory/adjust`
- [ ] Calculate discrepancy: `actual_qty - system_qty`
- [ ] Create `inventory_txn` (type: 'adjustment', note: reason)
- [ ] Reason enum: `damage`, `theft`, `measurement_error`, `personal_use`, `other`

---

### 14. Rate Limiting
**Priority: P1 | Effort: 1-2 hours**

slowapi is installed but not wired up.

**Tasks:**
- [ ] Add `Limiter` to `main.py`
- [ ] Rate limits:
  - Auth endpoints: 5/minute per IP
  - OCR scan: 10/minute per user
  - Bill creation: 30/minute per user
  - General API: 100/minute per user
- [ ] Custom key function: use JWT user_id if authenticated, IP if not

---

### 15. Recurring Expense Reminders
**Priority: P3 | Effort: 2-3 hours**

**Tasks:**
- [ ] Model: Add `recurring_frequency` field to Expense (monthly, weekly)
- [ ] `GET /api/v1/expenses/recurring` — list recurring expenses
- [ ] `GET /api/v1/expenses/recurring/due` — list due today
- [ ] One-tap confirm: `POST /api/v1/expenses/recurring/{id}/confirm` — create new expense from template

---

### 16. Deployment & DevOps
**Priority: P1 | Effort: 4-6 hours**

**Tasks:**
- [ ] `Dockerfile` for kts-api
- [ ] `docker-compose.yml` (api + postgres + redis)
- [ ] `.env.production` template
- [ ] Railway/Render deployment config
- [ ] Supabase PostgreSQL setup (or AWS RDS)
- [ ] CI/CD: GitHub Actions → auto-deploy on push to main
- [ ] Health check endpoint (already exists: `/health`)
- [ ] Alembic migration for production DB
- [ ] Logging: structured JSON logs for production
- [ ] Sentry integration for error tracking

---

## FRONTEND (React Native — Not Started)

### Sprint F1: Project Setup & Design System
**Effort: 1 week**

- [ ] `npx create-expo-app kts-app --template expo-template-blank-typescript`
- [ ] Project structure (see implementation_plan.md §4)
- [ ] Design tokens: colors (dark-mode ready), typography (Inter/Outfit), spacing
- [ ] Reusable components:
  - TextInput, NumberInput (decimal-aware), SearchInput
  - Card, ListItem, Badge (stock status colors)
  - BottomSheet, Modal, ActionSheet
  - Button (primary, secondary, ghost, danger)
  - EmptyState (illustrated), LoadingState, ErrorState
  - Header, FloatingActionButton
- [ ] API client layer (Axios + auth token injection + retry)
- [ ] State management (Zustand stores: auth, billDraft, ocrDraft, settings)
- [ ] Navigation shell (5 tabs: Home, Inventory, Bill, Ledger, More)

### Sprint F2: Auth & Onboarding
**Effort: 3-4 days**

- [ ] Login screen (phone input)
- [ ] OTP screen (6-digit verification)
- [ ] Business setup screen (name, GSTIN, address, state)
- [ ] PIN setup screen
- [ ] Firebase phone auth integration
- [ ] Token persistence (SecureStore)

### Sprint F3: Product, Customer, Company Screens
**Effort: 1 week**

- [ ] Product list (search by name + shortcode)
- [ ] Product form (all fields from PRD §4 F2.1)
- [ ] Product detail view
- [ ] HSN code → GST rate auto-lookup (embedded 8000 codes)
- [ ] Customer list + form + detail
- [ ] Company list + form + detail

### Sprint F4: OCR Camera + Verify UX
**Effort: 1.5 weeks (hardest frontend sprint)**

- [ ] Camera capture screen (full-screen, optimized for documents)
- [ ] Gallery import option
- [ ] Image quality checks (blur detection, lighting warning)
- [ ] Crop/rotate before upload
- [ ] Upload to S3 → call OCR endpoint
- [ ] OCR Verify screen — THE 4 STATES:
  - ✅ Confirming (high confidence) — read-only view + green "Confirm" button
  - 🟡 Needs-fix — amber-outlined suspect fields + cropped source image
  - ⚡ Auto-committed — toast notification, tap to review
  - ✋ Failed — "Couldn't read this bill" → manual entry pre-populated
- [ ] Learn-from-corrections (log every user edit for template learning)

### Sprint F5: Manual Purchase Entry + Purchase History
**Effort: 4-5 days**

- [ ] Manual purchase form (company, invoice#, items with discount/damaged_qty)
- [ ] Purchase list (filter by company, date, source badge: 📷 OCR / ✏️ Manual)
- [ ] Purchase detail view (with original bill image viewer)
- [ ] Full-screen bill image viewer

### Sprint F6: Bill Creation (Most-Used Screen)
**Effort: 1 week**

- [ ] "New Bill" screen — target: <30 seconds for 5 items
  - Customer selector (search + recents)
  - "Add Item" bottom sheet:
    - Product search (name + shortcode, autocomplete <500ms)
    - Quantity input (decimal support for loose stock)
    - Rate auto-filled from customer's price_tier
    - Available stock shown next to qty
    - GST auto-calculated
    - Line total instant display
  - Bill summary: Subtotal, CGST, SGST (or IGST), Grand Total
  - Payment: Full (cash/UPI) / Partial / Credit
- [ ] Bill history (filter by customer, date, status)
- [ ] Bill detail → re-share, view items, linked ledger entry

### Sprint F7: Bill Output + Share
**Effort: 3-4 days**

- [ ] PDF viewer (render PDF from API)
- [ ] Share via WhatsApp (react-native-share → WhatsApp intent)
- [ ] Share as image (screenshot)
- [ ] Email share (attachment)
- [ ] UPI QR code on invoice (if configured)

### Sprint F8: Ledger & Payments
**Effort: 1 week**

- [ ] Customer ledger screen (sales, payments, returns timeline)
- [ ] Company ledger screen (purchases, payments timeline)
- [ ] Outstanding dashboard:
  - Total Receivable / Payable / Net
  - Aging bars (0-30d green, 30-60d yellow, 60-90d orange, 90+ red)
  - Top 5 overdue customers
- [ ] Record payment screen (amount, mode, reference)
- [ ] WhatsApp payment reminder (one-tap from outstanding dashboard)

### Sprint F9: Inventory Dashboard
**Effort: 4-5 days**

- [ ] Stock dashboard (THE headline screen):
  - Product list with current stock (primary + secondary units)
  - Stock value at cost
  - Color-coded: 🟢 good, 🟡 low, 🔴 out
  - Sort by name / stock level / last purchase
  - Search/filter by category
- [ ] Low-stock alerts badge on home screen
- [ ] Stock movement log per product
- [ ] Stock adjustment screen (physical count entry)

### Sprint F10: Expenses + Home Dashboard
**Effort: 4-5 days**

- [ ] Add expense form (category, amount, date, payment mode, note, receipt photo)
- [ ] Expense list (filter by category, date range)
- [ ] Monthly category breakdown
- [ ] Home dashboard:
  - Today's summary card (sales, purchases)
  - Quick actions: "📷 Scan", "🧾 New Bill", "💳 Payment"
  - Low-stock widget (top 5)
  - Overdue payments widget (top 5 + one-tap reminder)
  - Recent activity timeline (last 10 actions)

### Sprint F11: Returns + Challan
**Effort: 3-4 days**

- [ ] Return screen (select original bill → select items → enter return qty)
- [ ] Challan screen (same as bill but no GST)
- [ ] "Convert to Invoice" button on challan detail

### Sprint F12: Search, Polish, Edge Cases
**Effort: 1 week**

- [ ] Global search (unified across products, customers, companies, bills, purchases)
- [ ] Edge case handling:
  - Zero-quantity bill → block
  - Negative stock → configurable (warn vs block)
  - Decimal rounding consistency
  - Very long product names on bill PDF
  - Customer without phone number
  - Network timeout → retry with idempotency key
- [ ] Error states (no internet, API timeout, OCR down)

### Sprint F13: Testing & Beta Prep
**Effort: 1 week**

- [ ] 20+ real supplier invoices through OCR pipeline
- [ ] OCR accuracy measurement (target: >90%)
- [ ] Performance: 10K products, search <500ms
- [ ] Bill creation <30 seconds (5 items)
- [ ] Test on Android 8, 10, 12, 14
- [ ] Test on low-end device (2GB RAM, 720p)
- [ ] App icon + splash screen (KTS branding)
- [ ] Onboarding walkthrough (3 screens)
- [ ] Empty states for all screens
- [ ] Play Store listing (screenshots, description, privacy policy)

### Sprint F14: Beta Launch
**Effort: 3-4 days**

- [ ] Deploy backend to production (Railway/Render)
- [ ] Release internal beta APK (20-30 real distributors)
- [ ] Instrument funnels (Mixpanel/Sentry):
  - Onboarding completion rate
  - First OCR scan success rate
  - First bill creation time
  - D1/D7/D30 retention
- [ ] Collect feedback via WhatsApp group
- [ ] Hot-fix sprint (1 week buffer)
- [ ] Production release to Play Store

---

## PHASE 2 (Post-MVP)

These are captured for future reference, NOT part of the current build:

- [ ] **Offline mode** — WatermelonDB + SQLite + CRDT sync
- [ ] **P&L / Analytics dashboard** — real profit margins using cost_basis data
- [ ] **Bluetooth thermal printing** — direct receipt printer support
- [ ] **Multi-user support** — owner + helpers with role-based access
- [ ] **Beat planning** — daily delivery route optimization
- [ ] **Barcode scanning** — scan product barcodes for quick billing
- [ ] **GSTR-1 export** — auto-generate GST return data
- [ ] **Bank statement reconciliation** — match payments with bank transactions
- [ ] **Supplier auto-ordering** — predict reorder based on consumption velocity
- [ ] **Hindi/Punjabi language support** — full i18n

---

## Effort Summary

| Area | Remaining Tasks | Estimated Effort |
|:---|:---|:---|
| Backend — Auth & Multi-tenancy | 3 tasks | ~10 hours |
| Backend — Returns & Challan | 2 tasks | ~8 hours |
| Backend — OCR Intelligence | 2 tasks | ~12 hours |
| Backend — Infrastructure | 5 tasks | ~14 hours |
| Backend — Other features | 4 tasks | ~10 hours |
| **Backend Total** | **16 tasks** | **~54 hours (~7 days)** |
| Frontend — All sprints | 14 sprints | **~10-12 weeks** |
| **Grand Total** | | **~12-14 weeks** |

> **Note:** Backend is ~80% complete. Frontend is 0% — that's the bulk of remaining work.
