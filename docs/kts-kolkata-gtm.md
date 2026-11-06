# KTS — Kolkata Go-to-Market and Remote Validation

> Companion to `kts-implementation-plan.md`. This replaces the in-person Phase 0 (25 interviews) with a **remote, low-time validation track** focused on Kolkata and nearby districts. Facts with sources are marked **[src]**. Everything else is a working assumption to confirm during validation and is marked **[assume]**.

---

## 1. Why Kolkata is a reasonable first market

| Factor | What we know | Implication for KTS |
|:--|:--|:--|
| Wholesale hubs | Burrabazar and Posta are the city's FMCG/grocery wholesale hubs. Kiranas pick up stock there directly when distributor delivery fails (Posta Merchants' Association, 2020) **[src: TOI]** | Distributors and wholesalers sit close together, so word of mouth spreads fast. Posta Merchants' Association is a channel to target |
| Brands based in Bengal | ITC, Emami, Bisk Farm, Anmol, Rupa, Keventer and Ganesh Consumer are all based in Kolkata. Ganesh alone runs 972 distributors through 28 C&F agents and 9 super stockists, serving 70,000+ outlets in East India **[src: Ganesh IPO note, Mar 2025]** | Many Kolkata distributors carry a mix of national and regional brands, which is exactly the multi-brand claims problem KTS targets |
| Advance-payment brands | Over 95% of Ganesh's general-trade sales are on advance payment **[src]** | The distributor's working capital is tied up at both ends: paid in advance to the brand, credit to retailers, and money stuck in claims. That makes claims recovery and collections the selling point |
| Quick commerce pressure | Kolkata is one of the 7 metros generating ~80% of q-commerce business **[src: ET, Apr 2025]**. AICPDF filed CCI complaints (Mar and Aug 2025) and says ~2 lakh kiranas have closed nationally **[src]** | Distributor margins are shrinking, so "which brand, route or retailer actually makes money" is more urgent. Frame KTS as a survival tool, not a nice-to-have |
| Claims friction is public | AICPDF publicly alleged Tata Consumer damage claims pending **over 15 months** and blocked investments (Oct 2025) **[src: Storyboard18]**. KPMG's 2025 CX report shows high variance in distributor satisfaction with scheme reimbursement **[src]** | Validates the claims pain without interviews. Use these articles in outreach messages |
| Language | **[assume]** Bengali-speaking owners in districts and suburbs; Hindi/Marwari owners dominate Burrabazar/Posta; accounts staff work in English | The report and PWA need English + Bengali + Hindi labels from day one (strings only, not translated data) |
| Books software | **[assume]** Tally dominates, with Busy common among Burrabazar traders and Marg among pharma-adjacent distributors | Confirm with the 10-question survey (§3.2) before building any connector other than Tally |

### 1.1 New regulatory hook: GST on scheme credit notes
A vendor source **[src: Kennect, 2026]** reports that from **1 Oct 2025, Section 34(2) of the CGST Act** ties the brand's tax reduction on a credit note to the **distributor reversing input tax credit**, and that **Circular 251/08/2025-GST (12 Sep 2025)** treats post-sale scheme discounts as discounts rather than a separate service. **Verify against the CBIC text before you depend on it.**

If confirmed, every scheme claim settled by credit note now has a GST side, and a mistake costs the distributor money twice. This changes the claims engine (plan §Phase 2):
- Tag each claim's settlement type: `discount_credit_note` | `commercial_credit_note` | `promotional_service_invoice`.
- For discount credit notes, show the ITC to reverse and the GSTR-2B/IMS month it appears in.
- Report: "credit notes received but ITC not yet reversed" (compliance risk) and "claims settled as commercial credit notes" (no GST impact).

This makes claims tracking partly a **compliance product**, which owners and their CAs will pay for more readily than for analytics alone.

---

## 2. Target segment (Kolkata-specific screen)

| Criterion | Value |
|:--|:--|
| Geography | Kolkata, Howrah, North and South 24 Parganas, Hooghly (one-day reach if a visit is ever needed) |
| Brands carried | ≥3, ideally a mix of one national brand (HUL/ITC/Dabur/Nestlé/Tata Consumer) and one or more regional brands (Bisk Farm, Anmol, Emami, Ganesh) |
| Turnover | ₹2–50 Cr |
| Books | Tally Prime / Tally ERP 9 (first), Busy (second) |
| Decision maker | Owner or owner's son/daughter who handles accounts; the next generation is the likeliest early adopter **[assume]** |

Not targeted first: super stockists for a single brand (they use the brand's DMS), pure Posta wholesalers with no brand schemes, and pharma distributors.

---

## 3. Remote validation track (replaces plan §2.2–2.4)

**Time budget:** ~4–6 hours a week from you, for 4 weeks. No market visits.

### 3.1 Lead sources that need no visits

| Source | How | Expected yield |
|:--|:--|:--|
| Kolkata Tally partners and Busy dealers | Offer each one a referral fee (e.g. 20% of the first year) for introducing distributor clients. They already have the relationship and the data access | Best channel. 3–5 partners → 20+ intros |
| CA firms handling distributor books | Same offer. The GST credit-note angle (§1.1) is a direct hook for CAs | 2–3 firms → 10+ intros |
| JustDial / IndiaMART listings | Search "FMCG distributor Kolkata", "biscuit distributor Howrah", etc. Build a sheet of 150 numbers | Cold leads; ~5% reply rate **[assume]** |
| WhatsApp/Facebook trade groups | Join West Bengal distributor and kirana trade groups; post a short Bengali/Hindi note offering a free claims check | Low cost, unpredictable |
| Brand sales staff on LinkedIn | ASMs/TSOs at Bisk Farm, Emami, Anmol and Ganesh know every distributor on their beat | Intros, plus insight into how brands process claims |
| Posta Merchants' Association, CWBTA, AICPDF's West Bengal unit | One email or phone call each: offer a free webinar or a members' discount | One "yes" can reach hundreds |

### 3.2 The 10-question phone/WhatsApp survey (10 minutes)
Replaces the 45-minute interview. Send as a voice-note-friendly WhatsApp message or a Google Form in English, Bengali and Hindi.

1. Which brands do you carry? (multi-select)
2. Billing/books software? (Tally / Busy / Marg / Vyapar / other / none)
3. Roughly how much money is pending in brand claims right now? (<₹50k / ₹50k–2L / ₹2–10L / >₹10L)
4. Oldest claim still pending? (<1 month / 1–3 / 3–6 / >6 months)
5. How do you track claims? (register / Excel / brand portal only / don't track)
6. Has your CA mentioned ITC reversal on scheme credit notes since Oct 2025? (yes / no / not sure)
7. Do you know net profit per brand? (yes, monthly / roughly / no)
8. How many retailers owe you money for more than 30 days? (0–10 / 10–50 / 50+)
9. Has quick commerce hurt your sales in the last year? (a lot / a little / no)
10. Would you share a Tally export to get a free claims and profit report? (yes / maybe / no)

### 3.3 Self-serve "free claims health check" (replaces the hand-built concierge)
Instead of building reports by hand in Excel, automate the concierge step with the Phase 0 Tally parser:
1. The distributor (or their Tally partner or CA) uploads a Tally XML Day Book and Ledger export, plus a photo or PDF of one brand claim statement.
2. KTS generates a 2-page PDF: claims ageing by brand, gross margin by brand, top 10 overdue retailers, and (if §1.1 is confirmed) credit notes awaiting ITC reversal.
3. You send it on WhatsApp with a 10-minute call to walk through it and make the pricing offer.

Engineering: ~5 dev-days on top of plan §2.5 (upload endpoint, parser, PDF template). It reuses the existing ReportLab PDF code and becomes the Phase 2 importer.

### 3.4 Pricing test
Same as plan §2.2 item 0.7 (₹1,500 / ₹2,500 / ₹3,500 per month, rotated), plus an option that tests the partner channel: **₹15,000/year billed through the Tally partner or CA**.

### 3.5 Revised decision criteria (4 weeks)

| Signal | Go | Pivot | Stop |
|:--|:--|:--|:--|
| Survey responses | ≥40 | 20–39 | <20 (fix the channel first, not the product) |
| Report ≥₹2L pending claims | ≥40% of respondents | 20–39% | <20% |
| Upload real data for the health check | ≥8 | 3–7 | <3 |
| Pay (any price) after the health check | ≥3 | 1–2 → lead with profitability or GST compliance instead of claims | 0 |
| Partners/CAs actively referring | ≥2 | 1 | 0 → reconsider the channel, not necessarily the product |

### 3.6 Weekly cadence

| Week | Your time (~5h) | Engineering |
|:--|:--|:--|
| 1 | Contact 10 Tally partners and 5 CAs; build the JustDial sheet; send the survey to 50 leads | Phase 1 auth/scoping fixes; Tally XML parser |
| 2 | Follow-ups; post in 3 trade groups; email the associations | Health-check upload + PDF |
| 3 | Run the first 5 health checks; make pricing offers | Fix parser issues on real data; save anonymised fixtures |
| 4 | 5–10 more health checks; write the go/pivot/stop memo | Phase 1 remainder |

---

## 4. Product changes for Kolkata

| Change | Phase | Effort |
|:--|:--|:--|
| UI strings in English, Bengali and Hindi (i18n keys in the PWA and PDF templates; Noto Sans Bengali / Devanagari fonts in ReportLab) | 2 | 2d |
| Claim settlement type + ITC reversal tracking (§1.1) | 2 (claims engine) | 3d |
| Brand master pre-seeded with common East India brands and their usual scheme types (Bisk Farm, Anmol, Emami, Ganesh, ITC, HUL) | 2 | 0.5d |
| Busy importer prioritised directly after Tally if the survey shows >25% Busy share | 2 | per plan |
| Festive-season view: Durga Puja (Sep–Oct) is the peak stocking and credit period, so add a "puja-season credit exposure" report | 2 | 1d |
| Partner/CA login: one partner manages several distributor accounts (read-only) | 2 | 2d |

---

## 5. Open questions to answer from survey data
1. Tally vs Busy share among Kolkata FMCG distributors.
2. Whether regional brands (Bisk Farm, Anmol, Ganesh) settle claims faster or slower than national ones. This decides which claims to show first.
3. Whether owners or their CAs are the actual buyer.
4. Whether the GST credit-note change (§1.1) is already causing pain, or whether CAs are absorbing it.

## 6. Sources
- TOI, "Market stabilizes as supply mechanism gets back on feet" (Mar 2020): Burrabazar/Posta hubs, Posta Merchants' Association.
- BP Wealth, Ganesh Consumer Products IPO note (2025): distributor network and advance-payment terms.
- Economic Times, "How entry of Blinkit, Swiggy Instamart and Zepto is transforming shopping habits" (Apr 2025).
- Economic Times, "FMCG distributors allege deep discounting by quick commerce firms with CCI" (Mar 2025); Outlook Business (Jul and Aug 2025).
- Storyboard18, "Tata Consumer Products distributors allege mismanagement" (Oct 2025).
- KPMG India CX Report 2025, FMCG section.
- Kennect, "FMCG sales incentive software" (2026): Section 34(2) / Circular 251/08/2025-GST summary. **Secondary source; verify with CBIC.**
