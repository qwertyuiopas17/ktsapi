# KTS (Karma Tattva Samiksha) — Phase-wise Implementation Plan

> **Version:** 2.0 (re-planned after market research, Nov 2026)
> **Repo:** `qwertyuiopas17/ktsapi` (FastAPI + SQLAlchemy 2 + Alembic)
> **Planning unit:** dev-days for one full-stack developer. Calendar weeks assume ~5 productive dev-days/week; interview time in Phase 0 is extra.

---

## 0. Why the plan changed

| Old plan (v1) | New plan (v2) |
|:--|:--|
| A general billing, OCR, inventory and ledger app for kirana/FMCG distributors | A **profit and claims system for multi-brand FMCG distributors**, which then grows into their main billing system |
| Pitch: "OCR is the front door" | OCR is a feature competitors already have. Pitch: **"Know which brand, route and retailer makes you money, and get your claim money back faster"** |
| Replace the distributor's books on day one | **Import from Tally/Busy/Marg first** so nobody types data twice. Replace billing only after users trust the product (Phase 3) |
| 10–12-week React Native app, 14 sprints | Web dashboard (PWA) for the owner and accountant first. A small mobile app for salesmen and collections comes in Phase 3 |
| No compliance roadmap | Batch/expiry, schemes, e-invoice and e-way bill are required before KTS can be anyone's main billing system |

**Target customer (ICP):** an FMCG distributor carrying **3 or more brands**, turnover **₹2–50 Cr**, who already uses Tally, Busy or Marg, runs 3–15 delivery routes, and has **₹2 lakh or more stuck in brand claims** at any time.

**Core promise:** in 15 minutes after importing their data, the owner sees
1. how much money each brand owes them in claims, and how old each claim is,
2. real net profit per brand, per route and per retailer,
3. who owes them money and a ready-to-send reminder for each.

---

## 1. Timeline at a glance

```
Week:        1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20+
Phase 0  ███████████                                                   Validate (interviews + concierge)
Phase 1  ███████████                                                   Secure & correct foundation
Phase 2           ██████████████████████                               Wedge: import, claims, profit, collections, web app
  GATE A                                 ▲ ≥10 paying, ≥70% weekly active
Phase 3                                  ███████████████████████████   Main billing system: batch, schemes, returns, e-invoice, salesman app
  GATE B                                                             ▲ ≥5 distributors billing 100% in KTS
Phase 4                                                                ███  Scale & monetise: credit, brand portal, channels
```

| Phase | Weeks | Dev-days (est.) | Must be true before moving on |
|:--|:--|:--|:--|
| 0 — Validate | 1–3 | ~3 (rest is interviews) | ≥3 distributors pay for the manually produced report |
| 1 — Foundation | 1–3 | 13–15 | Zero unauthenticated endpoints; cross-tenant test suite passes; staging deployed |
| 2 — Wedge | 4–10 | 33–38 | Gate A (see §4.9) |
| 3 — Main billing system | 11–19 | 40–45 | Gate B (see §5.10) |
| 4 — Scale & monetise | 20+ | ongoing | Business metrics, not a gate |

Phases 0 and 1 run **in parallel**: interviews in the mornings, engineering in the afternoons. Phase 1 work is needed whatever Phase 0 finds.

---

## 2. Phase 0 — Validate before building more (Weeks 1–3)

> **Superseded for the Kolkata launch:** the in-person interview track below has been replaced by the remote validation track in [`kts-kolkata-gtm.md`](kts-kolkata-gtm.md) §3 (phone/WhatsApp survey, Tally-partner and CA referrals, and a self-serve claims health check). The interview script and criteria below are kept as reference.

### 2.1 Goal
Prove, with money, that multi-brand distributors will pay for claims tracking and profitability before you write the Phase 2 code.

### 2.2 Activities

| # | Activity | Detail | Output |
|:--|:--|:--|:--|
| 0.1 | Pick one city/cluster | One wholesale market area you can visit physically (e.g. a mandi or wholesale market). Being local beats national reach at this stage. | City + list of 60 distributor leads |
| 0.2 | Find leads | Local distributor association chapter (AICPDF/FAIDA state bodies), Tally/Marg resellers, CAs who handle distributor books, brand ASMs | 60 leads, 25 interviews booked |
| 0.3 | Screen leads | ≥3 brands; ₹2–50 Cr turnover; uses Tally/Busy/Marg; owner-operated | Screened list |
| 0.4 | 25 structured interviews | Script in §2.3. Record, transcribe, tag. | Interview sheet (one row per distributor) |
| 0.5 | Collect sample data | With permission: Tally Day Book / Stock Summary / Ledger export, brand claim statements, scheme circulars, brand credit notes | Real data for 5–8 distributors (also used as import test fixtures in Phase 2) |
| 0.6 | Concierge MVP | Build each distributor's report **by hand in Excel/Sheets** from their exports: claims ageing per brand, gross and net margin per brand, top 10 loss-making retailers | 5 delivered reports |
| 0.7 | Pricing test | Offer the monthly report at ₹1,500 / ₹2,500 / ₹3,500 per month (rotate the price across distributors) | Conversion at each price |
| 0.8 | Write up decision | Go / pivot / stop against the criteria in §2.4 | 2-page memo |

### 2.3 Interview script (core questions)
1. Which brands do you carry? Which one gives the most revenue, and which the most headache?
2. What software do you use for billing and for books? Who enters the data?
3. Do you use any brand DMS (e.g. Shikhar or a brand-specific portal)? Do you enter data twice?
4. **How much money is currently stuck in pending claims? How old is the oldest claim?** Ask for an actual statement.
5. How do you track claims today (register, Excel, nothing)? How many get rejected?
6. Do you know your net profit per brand? Per route? How?
7. How many retailers owe you money for more than 30 days? How do you chase them?
8. Last software you paid for: what did it cost, and why did you buy it?
9. If a tool recovered your claims 4 weeks faster, what would it be worth per month?

### 2.4 Decision criteria

| Signal | Go | Pivot | Stop |
|:--|:--|:--|:--|
| Confirm claims pain with ≥₹2L outstanding | ≥15 of 25 | 8–14 | <8 |
| Share real data | ≥5 | 2–4 | <2 |
| Pay for the concierge report | ≥3 | 1–2 (and profitability is the bigger pull → lead with profit, not claims) | 0 |
| Main import source | Tells you which connector to build first (Tally vs Busy vs Marg) | — | — |

### 2.5 Engineering in Phase 0 (~3 dev-days)
- A script that parses Tally XML exports into CSV so the concierge reports take less time. This becomes the seed of the Phase 2 importer.
- Save anonymised exports as **test fixtures** in `tests/fixtures/imports/`.

---

## 3. Phase 1 — Secure and correct foundation (Weeks 1–3, 13–15 dev-days)

### 3.1 Goal
Make the existing backend safe to put real distributor data on, and fix correctness bugs that would otherwise corrupt the profit numbers later.

### 3.2 Workstream 1A — Authentication and tenant isolation (P0, 4 days)

| ID | Task | Files | Est. |
|:--|:--|:--|:--|
| 1A.1 | Create `app/deps.py` with a `RequestContext` dataclass (`user_id`, `business_id`, `role`) and a `get_ctx` dependency built on `get_current_user` | new `app/deps.py`, `app/services/auth_service.py` | 0.5d |
| 1A.2 | Remove every `BUSINESS_ID = uuid.UUID("0000…1")` constant. Add `dependencies=[Depends(get_ctx)]` at router level and pass `ctx.business_id` into every query | `app/routers/{bills,purchases,products,parties,expenses,dashboard}.py` | 1d |
| 1A.3 | Fix unscoped lookups: `get_bill`, `download_bill_pdf`, `whatsapp_share_link` (and any `filter(Model.id == id)` with no `business_id`). Add a helper `get_owned(db, Model, id, ctx)` that returns 404 on a mismatch | routers + new `app/utils/scoping.py` | 0.5d |
| 1A.4 | Child tables (`BillItem`, `PurchaseItem`, `InventoryTxn`) are always reached through a scoped parent. Add `business_id` to `InventoryTxn` for direct reporting queries | models + migration | 0.5d |
| 1A.5 | Real phone auth: the client signs in with Firebase Phone Auth and sends the ID token to `POST /auth/firebase`. The server verifies it with `firebase_admin.auth.verify_id_token` and issues a KTS JWT. Keep a dev-only stub behind `ENV=dev` | `app/routers/auth.py`, `app/config.py` | 1d |
| 1A.6 | Refresh tokens (30-day, rotating) plus a `token_version` column on `User` so you can revoke sessions; 4–6 digit PIN for quick unlock (bcrypt, already modelled) | models, auth router | 0.5d |
| 1A.7 | Role permissions: `require_role("owner","accountant")`, etc. Matrix: owner = all; accountant = all except users/settings; manager = no delete; delivery = own beat's bills and collections; warehouse = stock only | `app/deps.py` | 0.5d |

**Tenant isolation test suite** (`tests/test_tenancy.py`): create businesses A and B. For **every** route with an `{id}` path parameter, B's token on A's resource must return 404. Generate the route list from `app.routes` so new endpoints are covered automatically.

### 3.3 Workstream 1B — Invoice and tax correctness (P0, 3.5 days)

| ID | Task | Detail | Est. |
|:--|:--|:--|:--|
| 1B.1 | Financial-year invoice series | New table `document_series(business_id, doc_type, fy, prefix, next_number)`. Lock the row with `SELECT … FOR UPDATE` when issuing. FY runs April–March (`fy="2627"`). Number ≤16 chars, e.g. `INV/2627/00042`. Separate series for `invoice`, `credit_note`, `challan`, `receipt` | 1d |
| 1B.2 | Unique bill numbers per business | Change `Bill.bill_number unique=True` to `UniqueConstraint("business_id","bill_number")`. Right now two tenants can't both have `INV-2026-0001` | 0.25d |
| 1B.3 | GST rates with effective dates | New table `hsn_tax_rates(hsn_prefix, rate, cess_rate, effective_from, effective_to, note)`, loaded from `data/hsn_rates.json`. `lookup_gst_rate(hsn, on_date)`. Bill lines keep a copy of the rate used (already done) | 1d |
| 1B.4 | Fix rate data | 3401 toilet soap: 18% → 5% (GST 2.0). Add 3305 hair oil/shampoo 5%, 3306 toothpaste 5%. Keep 3402 detergents at 18%. Tobacco: add a cess column; confirm current tobacco treatment with a CA before release | 0.25d |
| 1B.5 | Invoice round-off | `round_off` column on `Bill` (to the nearest rupee); shown on the PDF | 0.25d |
| 1B.6 | Cancel bills, don't delete them | `status` column (`active`/`cancelled`) with `cancelled_at`, `cancel_reason`. Cancelling reverses stock and ledger entries. No hard deletes on financial documents | 0.75d |

### 3.4 Workstream 1C — Stock and money correctness (P0/P1, 2.5 days)

| ID | Task | Detail | Est. |
|:--|:--|:--|:--|
| 1C.1 | Row locks on stock | `stock_out`, `stock_in`, `adjust_stock`: `.with_for_update()` on `Inventory`. Concurrency test with 2 threads selling the last unit | 0.5d |
| 1C.2 | Correct txn types | `stock_in` currently labels every non-purchase as `return_in`. Pass `txn_type` explicitly | 0.25d |
| 1C.3 | Moving-average cost (base for Phase 2 profit) | Add `Inventory.avg_cost`. On purchase-in: `new_avg = (qty*avg + in_qty*net_landed_rate) / (qty+in_qty)`. `BillItem.cost_basis = avg_cost` at the time of sale (today it uses `product.purchase_price`, which is wrong) | 1d |
| 1C.4 | Credit-limit policy | `Business.credit_policy = warn|block`. Remove the dead `pass` branch; return `warnings[]` in the bill response | 0.25d |
| 1C.5 | Stock adjustment endpoint (old task #13) | `POST /api/v1/inventory/adjustments` (batch of counts with reason). Owner/warehouse roles only | 0.5d |

### 3.5 Workstream 1D — Platform and DevOps (P1, 3.5 days)

| ID | Task | Detail | Est. |
|:--|:--|:--|:--|
| 1D.1 | Alembic as the only source of the schema | Remove `create_all` at startup; write a baseline migration for current models | 0.5d |
| 1D.2 | Tests against Postgres | Move tests to `tests/`, shared `conftest.py`, Postgres via docker-compose / a CI service container. SQLite only for quick local runs | 0.5d |
| 1D.3 | Docker | `Dockerfile` (python:3.12-slim, uvicorn with gunicorn workers), `docker-compose.yml` (api + postgres + redis) | 0.5d |
| 1D.4 | CI | GitHub Actions: `ruff` + `pytest` on Postgres; block merge on failure | 0.5d |
| 1D.5 | Hosting | A managed Postgres plus a container host in an **India region** (Mumbai) to keep data local. Separate staging and prod | 0.5d |
| 1D.6 | Files | S3-compatible storage (old task #8) for invoice images, imports and PDFs; presigned upload/download URLs; private bucket | 0.5d |
| 1D.7 | Monitoring and backups | Sentry; structured JSON logs; nightly `pg_dump` to object storage, plus **one restore drill** that you document | 0.5d |
| 1D.8 | Rate limiting (old task #14) | slowapi: auth endpoints 5/min per phone and 20/min per IP; general 300/min per user | (included) |

### 3.6 Phase 1 acceptance criteria
- [ ] `GET /openapi.json` shows every non-auth, non-health route requires a bearer token.
- [ ] The tenancy suite passes for 100% of id-based routes.
- [ ] 50 concurrent bill creations produce 50 unique, gap-free numbers.
- [ ] Selling the last unit from two threads: one succeeds and one gets HTTP 400.
- [ ] Staging URL is live; Sentry receives a test error; backup restore is documented.
- [ ] `STATUS.md` is corrected (GST slabs, completion %, new plan).

---

## 4. Phase 2 — The wedge product (Weeks 4–10, 33–38 dev-days)

### 4.1 Goal
A distributor uploads their Tally/Busy/Marg data and, without changing how they bill, gets **claims tracking, real profitability and collections**. They should be willing to pay ₹1,500–3,000/month for it.

### 4.2 Architecture additions

```
            ┌──────────────── Owner / Accountant Web App (React + Vite PWA) ───────────────┐
            │  Import wizard · Claims board · Brand/Route/Retailer P&L · Collections · Home │
            └───────────────────────────────▲─────────────────────────────────────────────┘
                                            │ HTTPS + JWT (OpenAPI-generated TS client)
┌───────────────────────────────────────────┴─────────────────────────────────────────────┐
│ FastAPI                                                                                │
│  routers/  imports · brands · schemes · claims · analytics · collections · beats      │
│  services/ importers/{tally,busy,marg,excel} · matching · claims_engine · costing      │
│            profitability · reminders · payments_link                                   │
│  workers/  (RQ + Redis) import jobs · nightly fact rebuild · reminder sends            │
└───────────────┬─────────────────────────┬───────────────────────────┬──────────────────┘
            PostgreSQL               Object storage              WhatsApp / UPI links
  (OLTP + fact_sales_daily)     (exports, statements, PDFs)    (wa.me first, Cloud API later)
```

### 4.3 Workstream 2A — Data import (Weeks 4–5, 8 dev-days)

**Principle:** KTS reads from the distributor's existing system, so nobody re-types anything. Build the connector for whichever source Phase 0 showed most common first; Tally is the likely default.

**New tables**
```
import_batches   id, business_id, source[tally_xml|busy_xlsx|marg_xlsx|generic_xlsx|brand_statement],
                 period_from, period_to, file_key, status[uploaded|parsing|needs_mapping|committed|failed],
                 stats JSONB (rows, created, updated, skipped, errors), created_by, created_at
import_rows      id, batch_id, row_type[ledger|item|voucher|voucher_line], raw JSONB,
                 status[pending|matched|new|conflict|error], target_entity, target_id, error
external_refs    id, business_id, entity_type, entity_id, source, external_id (e.g. Tally GUID),
                 UNIQUE(business_id, source, entity_type, external_id)
```

| ID | Task | Detail | Est. |
|:--|:--|:--|:--|
| 2A.1 | Upload and job pipeline | `POST /imports` (multipart → object storage) creates a batch and queues a job; `GET /imports/{id}` shows progress | 1d |
| 2A.2 | Tally XML parser | Ledgers (with parent group → customer/supplier), Stock Items (HSN, GST, units, MRP), vouchers (Sales, Purchase, Credit Note, Debit Note, Receipt, Payment, Journal). Use the GUID for idempotency so re-imports update instead of duplicating | 2.5d |
| 2A.3 | Busy / Marg / generic Excel parser | Column-mapping templates saved per business (`import_mappings`) | 1.5d |
| 2A.4 | Matching | Parties by GSTIN first, then phone, then fuzzy name (`rapidfuzz`, threshold 90). Items by HSN + fuzzy name. Anything uncertain goes to a mapping screen | 1.5d |
| 2A.5 | Commit | Write canonical `Customer`, `Company`, `Product`, `Purchase`, `Bill`, `Payment`, and `LedgerEntry` (with `source='import'`) in one transaction per batch. Imported bills **do not** move KTS stock unless the business has set KTS as its stock source | 1d |
| 2A.6 | Incremental sync | Import by date range; a weekly "upload this week's Day Book" routine. (The Tally desktop connector comes in Phase 3) | 0.5d |

**Acceptance:** on the 5–8 real Phase 0 datasets, ≥98% of vouchers import without manual fixes, and sales/purchase totals reconcile with Tally reports to the rupee.

### 4.4 Workstream 2B — Brands and schemes (Week 5, 3 dev-days)

**Model changes**
```
brands       id, business_id, name, company_id (supplier/super-stockist), expected_margin_pct,
             claim_contact_name, claim_contact_phone, claim_sla_days (default 45), is_active
products     + brand_id FK, + mrp NUMERIC(12,2), + pack_size, + case_size
schemes      id, business_id, brand_id, code, name,
             type[pct_discount|flat_per_unit|free_qty|slab|price_drop|display|retailer_incentive],
             valid_from, valid_to, rules JSONB, reimbursable_pct (default 100), circular_file_key
scheme_products  scheme_id, product_id
```
Example `rules` for free-qty: `{"buy_qty": 10, "free_qty": 1, "free_product_id": null}`. For slab: `{"slabs":[{"min_value":5000,"pct":2},{"min_value":10000,"pct":3}]}`.

| ID | Task | Est. |
|:--|:--|:--|
| 2B.1 | CRUD for brands and schemes; auto-suggest brands from imported item names and stock groups | 1d |
| 2B.2 | Bulk-assign products to brands (by stock group, name prefix, or supplier) | 0.5d |
| 2B.3 | Scheme detection on imported bills: map discount lines and free-goods lines to the active scheme for that product and date | 1.5d |

### 4.5 Workstream 2C — Claims engine (Weeks 6–7, 7 dev-days) ★ core differentiator

**Tables**
```
claims             id, business_id, brand_id, claim_no (series 'CLM/2627/0001'),
                   claim_type[scheme|damage_expiry|price_protection|transport|display|other],
                   period_from, period_to, amount_claimed, amount_approved, amount_settled,
                   status[draft|submitted|acknowledged|partially_settled|settled|rejected|disputed|written_off],
                   submitted_at, acknowledged_at, settled_at, brand_reference, notes
claim_lines        id, claim_id, source_type[bill_item|sales_return|damage|manual], source_id,
                   scheme_id, product_id, qty, amount,
                   UNIQUE(source_type, source_id, claim_type)        -- blocks duplicate claims
claim_events       id, claim_id, from_status, to_status, note, file_key, created_by, created_at
claim_settlements  id, claim_id, settlement_type[credit_note|bank|adjusted_in_invoice],
                   reference, amount, settled_on, purchase_id/payment_id (nullable)
```
**Ledger:** add `entry_type` values `claim_raised`, `claim_settled`, `claim_written_off` on the brand's supplier (`party_type="company"`), so claims receivable appears next to what you owe the supplier.

| ID | Task | Detail | Est. |
|:--|:--|:--|:--|
| 2C.1 | Auto-generate draft claims | Each month (or on demand), per brand: collect unclaimed scheme lines, damage/expiry returns and price-drop stock into a draft claim | 1.5d |
| 2C.2 | Status workflow | Allowed transitions only; every change writes a `claim_event`; attach brand acknowledgement files | 1d |
| 2C.3 | Claim statement export | PDF plus Excel per brand, laid out the way brands usually ask (period, invoice no, retailer, SKU, qty, scheme, amount) | 1d |
| 2C.4 | Settlement matching | Imported brand credit notes and receipts are suggested against open claims (amount ±1%, brand, date window); user confirms; supports partial settlement | 1.5d |
| 2C.5 | Ageing and alerts | Buckets 0–30 / 31–60 / 61–90 / 90+; flag claims past the brand's `claim_sla_days`; weekly "cash stuck in claims" summary | 0.5d |
| 2C.6 | Rejection analysis | Rejected amount by brand and reason, so the distributor can push back on a specific brand | 0.5d |
| 2C.7 | Tests | Duplicate prevention, partial settlements, ledger balances, ageing boundaries | 1d |

**Endpoints**
```
GET    /api/v1/claims?brand_id&status&age_bucket
POST   /api/v1/claims/generate        {brand_id, period_from, period_to}
GET    /api/v1/claims/{id}            lines + events + settlements
POST   /api/v1/claims/{id}/transition {to_status, note, file_key}
GET    /api/v1/claims/{id}/statement?format=pdf|xlsx
GET    /api/v1/claims/settlement-suggestions
POST   /api/v1/claims/{id}/settlements
GET    /api/v1/claims/summary         totals by brand × age bucket
```

### 4.6 Workstream 2D + 2E — Costing and profitability (Weeks 7–9, 8 dev-days) ★ core differentiator

**New tables and changes**
```
beats        id, business_id, name, days (e.g. "MON,THU"), salesman_user_id, vehicle_id
vehicles     id, business_id, reg_no, type[own|hired], monthly_fixed_cost
customers    + beat_id FK (migrate from free-text beat_day), + cost_of_credit_exempt bool
expenses     + allocation_type[business|beat|vehicle|brand], + allocation_id
business     + cost_of_capital_pct (default 13.0), + overhead_allocation[revenue|drops|weight]
fact_sales_daily   business_id, date, brand_id, beat_id, customer_id, product_id,
                   qty, revenue_net, cogs, scheme_given, scheme_reimbursable, damages,
                   drops (bills), PRIMARY KEY(business_id, date, customer_id, product_id)
```

**Net contribution formula (per brand / route / retailer / SKU)**
```
Gross margin          = net revenue − COGS (moving average cost)
+ Scheme recoverable  = scheme_given × reimbursable_pct            (expected from brand)
− Scheme leakage      = scheme_given − recoverable − rejected claims
− Damages/expiry not recovered
− Cost to serve       = direct beat/vehicle costs + overhead share (by revenue | drops | weight)
− Credit cost         = avg outstanding × cost_of_capital_pct × days/365
= Net contribution  (and as % of revenue)
```

| ID | Task | Est. |
|:--|:--|:--|
| 2D.1 | Recompute `avg_cost` from history for imported data (back-fill job); recompute `cost_basis` on historical bill items | 1.5d |
| 2E.1 | Beats and vehicles CRUD; migration from `beat_day` strings; assign customers to beats in bulk | 1d |
| 2E.2 | Expense allocation UI fields; default rules (fuel → vehicle; salesman salary → beat) | 0.5d |
| 2E.3 | Nightly `fact_sales_daily` rebuild (RQ job) plus incremental refresh after an import | 1.5d |
| 2E.4 | Analytics endpoints: `GET /analytics/profit?dimension=brand|beat|customer|product&from&to`, `GET /analytics/customers/{id}/scorecard`, `GET /analytics/loss-makers` | 2d |
| 2E.5 | Reconcile against Tally gross profit for the same period (target within ±2%); show reasons for the difference | 0.5d |
| 2E.6 | Tests with fixed fixture data and known expected P&L | 1d |

### 4.7 Workstream 2F — Collections (Week 9, 4 dev-days)

```
promises_to_pay   id, business_id, customer_id, amount, promised_on, status[open|kept|broken]
reminders         id, business_id, customer_id, channel[whatsapp_link|whatsapp_api|sms], template,
                  sent_at, status, payment_link_id
payment_links     id, business_id, customer_id, amount, provider_ref, status, paid_at
```
| ID | Task | Est. |
|:--|:--|:--|
| 2F.1 | Retailer ageing (by bill, first-in-first-out allocation of receipts) and a retailer statement PDF | 1d |
| 2F.2 | Collection list per beat for today (who to visit, how much, promises due) | 0.5d |
| 2F.3 | WhatsApp reminders, v1 = `wa.me` deep link with pre-filled message (free, no approval needed). Hindi/English templates | 0.5d |
| 2F.4 | UPI payment links via a payment gateway; webhook marks payment received and creates a `Payment` and ledger entry | 1.5d |
| 2F.5 | Promise-to-pay capture and broken-promise alerts | 0.5d |

### 4.8 Workstream 2G — Owner web app (Weeks 4–10, parallel, 10–12 dev-days)

**Stack:** React + Vite + TypeScript + Tailwind, TanStack Query, React Router, `openapi-typescript` for a typed API client, PWA manifest, i18n (English + Hindi from day 1; add the regional language of your launch city).

| Screen | Content | Est. |
|:--|:--|:--|
| Login / OTP / PIN | Firebase phone auth, business switcher | 1d |
| Onboarding + import wizard | Upload → progress → mapping conflicts (parties, items, brands) → summary | 2d |
| Home | Cash stuck in claims · receivables > 30 days · this month's net profit · 3 actions to take | 1d |
| Claims board | Board view by status; filter by brand/age; claim detail with lines, events, statement download | 2d |
| Profit explorer | Table + bar chart by brand/beat/retailer/SKU; click through from brand → beat → retailer | 2d |
| Retailer scorecard | Revenue, margin, credit days, cost to serve, payment behaviour | 0.5d |
| Collections | Ageing table, today's list per beat, send reminder, payment link | 1.5d |
| Settings | Business profile, users and roles, brands, schemes, beats, vehicles, cost of capital | 1d |

**Design rules:** works on a 5-inch phone and a desktop; numbers always in ₹ lakh/crore format; every number can be clicked through to the vouchers behind it (trust).

**KTS's own subscription billing (1 day):** subscriptions through a payment gateway, a 14-day trial, and three plans (see §8).

### 4.9 Gate A — required before Phase 3
- [ ] **≥10 paying distributors** (not friends, not free).
- [ ] **≥70% of owners active weekly** for 6 consecutive weeks.
- [ ] At least **2 documented wins**: a claim recovered or escalated thanks to KTS, or a loss-making route or retailer fixed.
- [ ] Import accuracy ≥98%; P&L reconciles with Tally within ±2%.
- [ ] Monthly cancellations <10%.

If Gate A fails: stay in Phase 2. Interview the inactive users, cut features, and change the pitch (claims vs profit). **Do not** build billing to fix a retention problem.

---

## 5. Phase 3 — Become the main billing system (Weeks 11–19, 40–45 dev-days)

### 5.1 Goal
Let distributors **bill in KTS**, so data arrives in real time instead of through weekly imports, and KTS becomes hard to replace. This phase reuses most of your existing billing, purchase and inventory code.

### 5.2 Workstream 3A — Batches, expiry, MRP, godowns (6 dev-days)
```
godowns            id, business_id, name, address       (use the existing Inventory.godown_id placeholder)
batches            id, business_id, product_id, batch_no, mfg_date, expiry_date, mrp, landed_cost
inventory_batches  id, business_id, batch_id, godown_id, qty_primary      -- replaces single-row stock
```
- First-to-expire-first-out (FEFO) allocation in `stock_out`: pick the nearest unexpired batch first, with manual override.
- Near-expiry report (30/60/90 days) that **creates expiry claims** for brands that allow returns.
- Migration: existing `Inventory.qty_primary` becomes one "OPENING" batch per product.

### 5.3 Workstream 3B — Schemes applied during billing (6 dev-days)
- When a bill line is created, evaluate active schemes for product, customer, date and quantity: percentage discount, flat per unit, free quantity (adds a free line with zero value), slab on bill value, retailer-specific prices.
- Separate **trade discount** (before GST) from **cash discount** (after invoice, via credit note).
- Every scheme line automatically becomes a `claim_line`, so claims work in real time.
- Have a CA review the GST treatment of free goods and post-sale discounts before release.

### 5.4 Workstream 3C — Returns, credit notes, debit notes (old task #4, 5 dev-days)
- Sales return → credit note (`bill_type='credit_note'`, `original_bill_id`), using its own number series.
- Saleable returns go back to the original batch; damaged/expired returns go to a "damaged" location and **create a claim line**.
- Ledger reversal and outstanding update; partial returns allowed.
- Respect the legal time limit for credit notes (Section 34); warn when issuing late.
- Purchase returns / debit notes to brands.

### 5.5 Workstream 3D — Delivery challan and van load (old task #5, 3 dev-days)
- Challan with no tax, using its own series; convert to an invoice (one or many) later.
- Van-load sheet per beat (SKU totals across that beat's bills), plus delivery confirmation (delivered / partial / refused, with reason).

### 5.6 Workstream 3E — E-invoice, e-way bill, GST returns (8 dev-days)
- Connect through a **GSP (GST Suvidha Provider) / ASP**, not directly to the government portal (direct access requires static IPs and a heavy setup).
- Generate the IRN with the signed QR on the invoice PDF; cancel within the allowed window; handle errors and retries with an idempotency key.
- E-way bill from the IRN for consignments above the threshold; update vehicle details (Part-B) from the van-load sheet. Include Ship-to GSTIN per the August 2026 API advisory.
- For businesses with AATO ≥ ₹10 Cr, enforce the **30-day IRP reporting window** (warn on bills older than 25 days).
- GSTR-1 JSON export plus HSN summary; reconcile with the GSTR-2B download for purchases (optional).
- Business setting `einvoice_enabled` (auto-suggested if turnover is above ₹5 Cr).

### 5.7 Workstream 3F — Salesman and delivery mobile app (8 dev-days)
- **Expo (React Native) or PWA.** Choose based on Phase 2 usage: a PWA is enough unless Bluetooth printing or heavy offline use is required. If printing is needed, choose Expo.
- Offline-first queue (SQLite on the device). Orders and collections sync when the phone is back online; the server rejects duplicates using client-generated UUIDs.
- Screens: today's beat → retailer list → order taking (stock, scheme preview, credit warning) → collection receipt → day-end summary.
- Orders arrive as `sales_orders` that the owner approves into bills (or are auto-billed if the owner turns that on).
- Bluetooth thermal printing (ESC/POS, 58/80mm) for on-the-spot bills and receipts.

### 5.8 Workstream 3G — Tally write-back connector (4 dev-days)
- A small Windows tray app (or a script) that posts KTS vouchers to Tally's local XML server, so the CA's books stay in Tally without double entry.
- Mapping of KTS ledgers to Tally ledgers; sync log; retry on failure.
- This is what lets a distributor switch billing to KTS without changing accountants.

### 5.9 Workstream 3H — OCR, re-scoped (2–3 dev-days)
- Keep the existing Groq Vision service. Simplify the planned 4-state confidence gating to 3 states: **auto-filled → needs review → failed**.
- Remember corrections per supplier (product and party name aliases), the same idea as competitors. **Drop** the Google Document AI fallback and the separate template-learning engine.
- New, higher-value use: **read brand credit-note statements and claim settlement letters** and match them to open claims.

### 5.10 Gate B — required before Phase 4
- [ ] ≥5 distributors bill **100%** in KTS for 4 consecutive weeks.
- [ ] Zero unresolved e-invoice/e-way bill failures older than 24 hours.
- [ ] A 10-line bill takes <30 seconds on a mid-range Android phone (median).
- [ ] Tally write-back error rate <0.5% of vouchers.
- [ ] ≥30 paying customers in total; monthly cancellations <5%.

---

## 6. Phase 4 — Scale and monetise (Week 20+)

### 6.1 Embedded credit (largest revenue upside)
- Model: KTS acts as a **Lending Service Provider** for a regulated bank/NBFC partner, using OCEN and Account Aggregator consent flows. KTS never lends from its own money.
- Products, in order:
  1. **Advance against approved claims.** The distributor gets cash now against claims the brand has acknowledged. This is unique to KTS because you hold the claims data.
  2. Inventory finance against brand purchase orders.
  3. Retailer credit lines (the distributor gets paid upfront; the lender collects).
- Compliance: RBI Digital Lending rules (key fact statement, consent records, default-loss guarantee caps, grievance officer), explicit consent under the DPDP Act. Budget for legal review before launch.
- Revenue: a referral or revenue share per loan from the lending partner.

### 6.2 Brand portal (network effect)
- Free portal for regional and small brands: they **acknowledge and settle claims online** and see opted-in, aggregated secondary sales from distributors on KTS.
- Each brand that joins pulls in its other distributors. Later, charge brands for analytics and scheme tools.
- Strict rule: distributors control sharing per brand; no data is sold without opt-in.

### 6.3 Product depth
- Multiple godowns and GSTINs, approval workflows (discount above X% needs owner approval), purchase suggestions from stock velocity, price-list management, barcode billing, customer-facing ordering link (catalogue on WhatsApp).

### 6.4 Go-to-market at scale
- Partner programme for CAs and Tally/Marg resellers (revenue share).
- Distributor association chapters; city-by-city launches; Hindi plus regional-language onboarding videos.
- Referral credits: one free month per referred paying distributor.

### 6.5 Platform hardening
- Postgres Row-Level Security on `business_id` as a second layer of isolation; read replica for analytics; partition the largest tables by FY; per-tenant data export (DPDP right to access/erase); external security review.

---

## 7. Cross-cutting standards (all phases)

| Area | Standard |
|:--|:--|
| Money | `Decimal` everywhere (Pydantic `condecimal`), never `float`. Round per line, then round off the invoice total |
| Time | Store UTC; business logic (FY, due dates, "today") in `Asia/Kolkata` |
| Ids and duplicates | UUIDs; client-generated ids for mobile/offline writes; idempotency key on payment and e-invoice calls |
| Auditing | `created_by`, `updated_by`, and an event history for financial documents; no hard deletes |
| Tenancy | Every query is scoped by `ctx.business_id`; the tenancy test suite runs in CI |
| Testing | Unit tests for services (GST, costing, claims, schemes); API tests per router; golden-file tests for imports and P&L; target ≥75% coverage on `services/` |
| Migrations | One Alembic migration per PR; must be reversible; run on staging before prod |
| Releases | Weekly release to staging, then prod after a smoke test; feature flags per business for risky features (e-invoice, auto-billing) |
| Privacy | DPDP Act: consent text at signup, data-processing terms, export/delete per business, data stored in India |
| Support | In-app WhatsApp support number; personal onboarding call for every new distributor in Phases 2–3 |

---

## 8. Pricing and unit economics (assumptions to validate in Phase 0)

| Plan | Price (est.) | Includes |
|:--|:--|:--|
| **Insight** | ₹1,500/month (or ₹15,000/yr) | Import, claims, profit, collections; 3 users |
| **Operate** | ₹3,000/month (or ₹30,000/yr) | + billing, batches, schemes, returns, e-invoice/e-way bill, salesman app (5 salesmen), Tally write-back |
| **Scale** | ₹6,000+/month | + multiple godowns/GSTINs, extra salesmen, approvals, priority support |

Variable costs to include in the price: e-invoice/e-way bill GSP fees per document, WhatsApp Cloud API per-conversation fees (Phase 2 uses free `wa.me` links), payment gateway fees, hosting.

**Targets:** customer acquisition cost recovered within 6 months; gross margin ≥75%; ≥3,000 paying distributors (~₹6–9 Cr ARR) by year 4 before any lending revenue. These are planning estimates, not forecasts.

---

## 9. What happens to the old 16-task backlog

| Old # | Task | New place |
|:--|:--|:--|
| 1 | Wire JWT to all endpoints | **Phase 1** 1A.2 |
| 2 | Real Firebase auth | **Phase 1** 1A.5 |
| 3 | Multi-tenancy | **Phase 1** 1A.2–1A.4 + tenancy suite |
| 4 | Bill return / credit note | **Phase 3** 3C |
| 5 | Delivery challan | **Phase 3** 3D |
| 6 | OCR confidence gating (4 states) | **Phase 3** 3H, simplified to 3 states |
| 7 | Per-supplier template learning | **Dropped** → correction memory in 3H |
| 8 | S3 image upload | **Phase 1** 1D.6 |
| 9 | Google Document AI fallback | **Dropped** |
| 10 | Payment reminder scheduler | **Phase 2** 2F |
| 11 | Bulk product import | **Absorbed** into Phase 2 2A (full data import) |
| 12 | Global search | Phase 3 (small task with the web app's command bar) |
| 13 | Stock adjustment endpoint | **Phase 1** 1C.5 |
| 14 | Rate limiting | **Phase 1** 1D.8 |
| 15 | Recurring expense reminders | **Dropped** (re-evaluate after Gate B) |
| 16 | Deployment | **Phase 1** 1D |
| — | React Native app, 14 sprints | **Replaced** by the Phase 2 web PWA plus the Phase 3 salesman app |

---

## 10. Week-by-week calendar

| Week | Engineering | Market |
|:--|:--|:--|
| 1 | 1A auth + tenancy, tenancy suite | Choose city, build 60 leads, book interviews |
| 2 | 1B invoice series, GST rate table, cancel instead of delete; 1C locks + moving-average cost | 10 interviews; collect exports |
| 3 | 1D Docker, CI, staging, backups, S3; Tally XML script | 15 interviews; 5 concierge reports; pricing test; **go/no-go memo** |
| 4 | 2A upload pipeline + Tally parser; web app shell + auth | Deliver reports, convert to paid |
| 5 | 2A Busy/Marg/Excel + matching + commit; 2B brands/schemes; import wizard UI | Onboard the first 3 paying users on staging data |
| 6 | 2C claims generation + workflow; claims board UI | Weekly calls with pilot users |
| 7 | 2C statements + settlement matching + ageing; 2D cost back-fill | Recruit pilots 4–8 |
| 8 | 2E beats/vehicles/allocation, fact table, analytics API | — |
| 9 | 2E profit explorer UI + scorecard; 2F collections + payment links | Recruit pilots 9–12 |
| 10 | Hardening, Tally reconciliation, KTS subscriptions; **Gate A review** | Case studies from the 2 documented wins |
| 11–12 | 3A batches/expiry/godowns | Pick 5 distributors for the billing pilot |
| 13 | 3B schemes during billing | CA review of scheme GST treatment |
| 14 | 3C returns/credit notes; 3D challan/van load | — |
| 15–16 | 3E e-invoice/e-way bill via GSP; GSTR-1 export | GSP sandbox certification |
| 17–18 | 3F salesman app + offline + printing | Field test with 2 distributors' salesmen |
| 19 | 3G Tally write-back; 3H OCR re-scope; **Gate B review** | Pricing review for the Operate plan |
| 20+ | Phase 4: lending partner integration, brand portal | CA/reseller partner programme; second city |

---

## 11. Key metrics to track from Phase 2

| Metric | Definition | Target |
|:--|:--|:--|
| Activation | % of new businesses with a completed import + ≥1 brand + ≥1 claim generated within 7 days | ≥60% |
| Owner weekly activity | Owners who open Home or Claims each week | ≥70% |
| Claims under management | ₹ value of open claims tracked in KTS | Grow every month |
| Claim cycle time | Median days from claim submitted to settled, before vs after KTS | −25% within 3 months |
| Receivables >30 days | ₹ value per customer, before vs after | −15% within 3 months |
| Paid conversion | Trials that become paying | ≥30% |
| Monthly cancellations | Paying customers lost per month | <5% by Phase 3 |

---

## 12. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|:--|:--|:--|:--|
| Distributors won't pay for analytics alone | Medium | High | Phase 0 pricing test; Gate A; lead with ₹ recovered (claims), not dashboards |
| Import breaks on messy Tally data | High | High | Real fixtures from Phase 0; mapping UI; golden-file tests; personal onboarding |
| Brands make claims harder (portals, rejections) | Medium | Medium | Rejection analytics and statements give the distributor evidence; brand portal in Phase 4 |
| Distributor channel shrinks (quick commerce, brands going direct) | Medium | High | Target multi-brand distributors (they consolidate and gain share); credit and brand portal reduce dependence on headcount growth |
| Competitors (Vyapar, myBillBook, Marg) add claims features | Medium | Medium | Move fast in one city; depth (settlement matching, profit including credit cost and cost to serve) plus Tally write-back; claims data becomes the base for credit |
| GST/e-invoice rules change | High | Medium | Rate table with effective dates; e-invoice through a GSP; CA advisor on retainer |
| Data breach / tenant leak | Low | Very high | Tenancy suite in CI, RLS in Phase 4, least-privilege roles, encrypted backups, external review |
| Solo-developer bandwidth | High | High | Strict cut list (§9); no Phase 3 before Gate A; hire a part-time field onboarding person once paid users reach 10 |

---

## 13. Immediate next 10 actions

1. Correct `STATUS.md` (GST slabs, the new positioning) and commit this plan to the repo.
2. Create `app/deps.py` and remove `BUSINESS_ID` from the first router (`bills.py`); write the tenancy test.
3. Apply the same change to the remaining routers.
4. Add the `document_series` table and migration; switch `_next_bill_number` to the financial year.
5. Change `Bill.bill_number` uniqueness to per business.
6. Add `Inventory.avg_cost` and take `cost_basis` from it.
7. Dockerfile + docker-compose + GitHub Actions on Postgres.
8. Choose the launch city; build the 60-lead list.
9. Book the first 10 interviews; prepare the script (§2.3).
10. Write the Tally XML → CSV script for concierge reports.
