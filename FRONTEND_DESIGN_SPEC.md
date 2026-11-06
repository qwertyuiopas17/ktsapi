# KTS Mobile App — Frontend Design Specification

> A professional distributor management app built for speed, clarity, and trust.
> No decorative gradients. No emoji icons. No AI-generated aesthetic.
> Every pixel earns its place.

---

## 1. Design Philosophy

### Principles
1. **Data density over decoration** — Distributors manage 200+ products, 100+ customers. The UI must show maximum information per screen without feeling cramped.
2. **Speed is the feature** — Bill creation under 30 seconds for 5 items. Every tap must feel instant. No loading spinners longer than 300ms for cached data.
3. **Trust through precision** — Financial apps must feel exact. Numbers are always formatted consistently. Totals always reconcile visually. No rounding surprises.
4. **Monochrome first, color with intent** — Color is reserved for status indicators and destructive actions. The rest is neutral.
5. **Familiar to the user** — Distributors use WhatsApp, Google Pay, PhonePe daily. Borrow interaction patterns from these apps, not from Silicon Valley design trends.

### What This App Is NOT
- Not a consumer fintech app with card carousels and rounded corners everywhere
- Not a dashboard-heavy analytics tool (that's Phase 2)
- Not a design portfolio piece — it's a work tool used 50+ times per day in harsh lighting conditions

---

## 2. Color System

### Core Palette
```
Background
  --surface-primary:     #FFFFFF        White — main content areas
  --surface-secondary:   #F5F6F8        Off-white — screen backgrounds, list separators
  --surface-elevated:    #FFFFFF        Cards, sheets, modals (elevated via shadow)

Text
  --text-primary:        #1A1D21        Near-black — all primary text
  --text-secondary:      #5E6268        Medium grey — labels, timestamps, helper text
  --text-tertiary:       #9BA1A8        Light grey — placeholders, disabled text
  --text-inverse:        #FFFFFF        White text on dark backgrounds

Borders & Dividers
  --border-default:      #E1E4E8        Standard borders (inputs, cards, table lines)
  --border-strong:       #C8CCD0        Emphasized borders (focused inputs)
  --divider:             #ECEEF0        List dividers, section separators

Brand
  --brand-primary:       #1B6EF3        Blue — primary actions, links, selected tabs
  --brand-pressed:       #1558C5        Darker blue — pressed state
  --brand-subtle:        #EBF2FE        Light blue — selected row backgrounds, chips

Status (used ONLY for status indicators — never decorative)
  --status-success:      #1A8754        Green — paid, in stock, confirmed
  --status-success-bg:   #E8F5E9        Light green background
  --status-warning:      #C27803        Amber — low stock, partial payment, needs review
  --status-warning-bg:   #FFF8E1        Light amber background
  --status-danger:       #D32F2F        Red — out of stock, overdue, failed, delete
  --status-danger-bg:    #FFEBEE        Light red background
  --status-info:         #5E6268        Grey — neutral status, draft, pending
  --status-info-bg:      #F5F6F8        Light grey background
```

### Dark Mode (Phase 2)
Not in v1. The app will ship light-only. Dark mode is deferred because distributor shops have mixed lighting — a high-contrast light theme is more readable in direct sunlight and fluorescent tube lighting.

---

## 3. Typography

### Font Stack
```
Primary:        Inter (Google Fonts)
Monospace:      JetBrains Mono — for currency amounts, invoice numbers, GSTINs
Fallback:       System default (Roboto on Android)
```

### Type Scale
```
Display         28px / 700 weight / -0.02em tracking    — Screen titles (rare)
Heading 1       22px / 600 weight / -0.01em              — Section headers
Heading 2       18px / 600 weight / 0                    — Card titles
Heading 3       16px / 600 weight / 0                    — Sub-section headers

Body Large      16px / 400 weight / 0                    — Primary content
Body            14px / 400 weight / 0                    — Standard body text
Body Small      13px / 400 weight / 0                    — Secondary info
Caption         12px / 400 weight / 0.01em               — Labels, timestamps

Currency        16px / 600 weight / JetBrains Mono       — All monetary values
Currency Large  22px / 700 weight / JetBrains Mono       — Totals, outstanding
Currency Small  13px / 500 weight / JetBrains Mono       — Line item amounts
Code            13px / 400 weight / JetBrains Mono       — Invoice numbers, GSTINs
```

### Currency Formatting
- Always use the Indian numbering system: 1,00,000 (not 100,000)
- Symbol: use plain text "Rs" followed by a non-breaking space, NOT the rupee sign (some older phones render it as a box)
- Decimal: always show 2 decimal places for amounts (Rs 1,500.00, not Rs 1500)
- Negative amounts: prefix with minus, colored in --status-danger (Rs -500.00)

---

## 4. Iconography

### Icon System
- **Library:** Phosphor Icons (regular weight, 24px default)
- **Style:** Outline only. No filled icons except for active tab bar items.
- **Stroke:** 1.5px consistent stroke weight
- **Size:** 20px for inline, 24px for buttons/tabs, 32px for empty states

### Key Icon Mapping
```
Home / Dashboard        House
Inventory / Stock       Package
New Bill / Billing      Receipt
Ledger / Payments       BookOpen
More / Settings         DotsThreeVertical

Scan Purchase           Camera
Manual Entry            PencilLine
Add Product             Plus
Search                  MagnifyingGlass
Filter                  Funnel
Sort                    SortAscending

Customer                User
Company / Supplier      Buildings
Payment                 CurrencyInr

Low Stock Alert         Warning
Overdue                 Clock
WhatsApp Share          WhatsappLogo (only place a brand icon is used)
PDF Download            FilePdf
Phone Call              Phone
Delete                  Trash
Edit                    PencilSimple
Back                    CaretLeft
Close                   X
Checkmark               Check
```

---

## 5. Component Library

### 5.1 Buttons

```
PRIMARY BUTTON
  ┌──────────────────────────────┐
  │       Create Bill            │   bg: --brand-primary
  └──────────────────────────────┘   text: white, 14px/600
                                     height: 48px
                                     radius: 8px
                                     full-width on mobile forms

SECONDARY BUTTON
  ┌──────────────────────────────┐
  │       Add Another Item       │   bg: transparent
  └──────────────────────────────┘   border: 1px --border-default
                                     text: --text-primary, 14px/500
                                     height: 44px

DANGER BUTTON
  ┌──────────────────────────────┐
  │       Delete Product         │   bg: --status-danger
  └──────────────────────────────┘   text: white
                                     Only for destructive, confirmed actions

TEXT BUTTON (link-style)
  Cancel   |   View All   |   Clear     text: --brand-primary, 14px/500
                                         no background, no border
                                         underline on press

ICON BUTTON
  [ icon ]                               40x40px touch target
                                         24px icon, no label
                                         Used in headers, list actions
```

### 5.2 Input Fields

```
TEXT INPUT (default)
  ┌─────────────────────────────────────┐
  │ Label                               │   label: 12px/500 --text-secondary
  │ ┌─────────────────────────────────┐ │   positioned above input
  │ │ Placeholder text                │ │
  │ └─────────────────────────────────┘ │   input: 14px/400 --text-primary
  │                                     │   height: 48px
  │ Helper text or error                │   border: 1px --border-default
  └─────────────────────────────────────┘   radius: 8px
                                            focus: border --brand-primary (2px)
                                            error: border --status-danger + red helper

NUMBER INPUT (for quantities, amounts)
  ┌─────────────────────────────────────┐
  │ Quantity                            │
  │ ┌─────────────────────────┐ ┌────┐ │
  │ │ 10.5                    │ │ Kg │ │   right-aligned text
  │ └─────────────────────────┘ └────┘ │   unit suffix chip
  └─────────────────────────────────────┘   numeric keyboard only

SEARCH INPUT
  ┌─────────────────────────────────────┐
  │ [search icon]  Search products...   │   icon left-aligned
  └─────────────────────────────────────┘   height: 44px
                                            bg: --surface-secondary
                                            radius: 8px
                                            no border (filled style)
```

### 5.3 Cards

```
STANDARD CARD
  ┌─────────────────────────────────────────────┐
  │  Toor Dal Premium                    TDP    │   title: 16px/600
  │  HSN: 0713  |  GST: 5%                     │   subtitle: 13px/400 --text-secondary
  │                                             │
  │  Stock: 250 Kg (5 Bags)              Rs 90  │   trailing: currency
  │  ━━━━━━━━━━━━━━━━━━━ (green bar)            │   stock bar (visual fill)
  └─────────────────────────────────────────────┘
    shadow: 0 1px 3px rgba(0,0,0,0.08)
    radius: 10px
    padding: 16px
    bg: white
    border: none (shadow provides separation)
    tap: entire card is touchable

COMPACT LIST ITEM (for search results, selectors)
  ┌─────────────────────────────────────────────┐
  │  Toor Dal Premium              5 Bags  >    │   single line
  └─────────────────────────────────────────────┘   height: 56px
    divider: 1px --divider (inset 16px from left)
    no shadow, no radius
    used inside flat lists
```

### 5.4 Status Badges

```
PAID        [ Paid ]        bg: --status-success-bg, text: --status-success
PARTIAL     [ Partial ]     bg: --status-warning-bg, text: --status-warning
CREDIT      [ Credit ]      bg: --status-danger-bg,  text: --status-danger
DRAFT       [ Draft ]       bg: --status-info-bg,    text: --status-info

IN STOCK    [ In Stock ]    bg: --status-success-bg
LOW STOCK   [ Low ]         bg: --status-warning-bg
OUT         [ Out ]         bg: --status-danger-bg

Badge style:
  padding: 4px 10px
  radius: 4px
  font: 11px/600 uppercase tracking 0.04em
  no border
```

### 5.5 Bottom Sheet

```
  ┌─────────────────────────────────────────────┐
  │  ──── (drag handle, 32px wide, 4px tall)    │
  │                                             │
  │  Sheet Title                        [X]     │
  │  ─────────────────────────────────────────  │
  │                                             │
  │  Content area                               │
  │  (scrollable if content exceeds 60vh)       │
  │                                             │
  │  ┌─────────────────────────────────────┐    │
  │  │          Primary Action             │    │
  │  └─────────────────────────────────────┘    │
  └─────────────────────────────────────────────┘
    backdrop: rgba(0,0,0,0.4)
    radius: 16px 16px 0 0 (top corners only)
    max-height: 85vh
    spring animation on open/close (200ms)
```

### 5.6 Toast / Snackbar

```
  ┌───────────────────────────────────────────────┐
  │  [check icon]  Bill #INV-2026-0042 created    │
  └───────────────────────────────────────────────┘
    position: bottom, 16px above tab bar
    bg: #1A1D21 (near-black)
    text: white, 14px/500
    radius: 8px
    auto-dismiss: 3 seconds
    action link (optional): "View" in --brand-primary on dark bg
```

---

## 6. Navigation Structure

### Tab Bar (5 tabs)
```
  ┌─────────┬─────────┬─────────┬─────────┬─────────┐
  │  Home   │  Stock  │   +     │ Ledger  │  More   │
  │  [icon] │  [icon] │ [icon]  │ [icon]  │ [icon]  │
  └─────────┴─────────┴─────────┴─────────┴─────────┘

  Center tab (+) is the "New Bill" quick-action (slightly larger, 56px circle)
    bg: --brand-primary
    icon: Plus, white, 28px
    No label

  Active tab:  --brand-primary icon (filled variant) + label
  Inactive:    --text-tertiary icon (outline) + label
  Tab bar:     bg white, top border 1px --border-default
  Height:      56px + safe area inset
```

### Stack Navigation
```
Home Tab
  ├── HomeScreen
  ├── NotificationsScreen
  └── GlobalSearchScreen

Stock Tab
  ├── StockDashboardScreen
  ├── ProductListScreen
  │   └── ProductFormScreen (add/edit)
  │   └── ProductDetailScreen
  │       └── StockMovementScreen
  └── StockAdjustScreen

Bill Tab (center +)
  ├── NewBillScreen
  ├── BillListScreen
  │   └── BillDetailScreen
  │       └── BillPdfScreen
  │       └── ReturnScreen
  └── ChallanScreen

Ledger Tab
  ├── OutstandingScreen
  ├── CustomerLedgerScreen
  ├── CompanyLedgerScreen
  └── RecordPaymentScreen

More Tab
  ├── PurchaseListScreen
  │   └── ScanPurchaseScreen (camera)
  │   └── OcrVerifyScreen
  │   └── ManualPurchaseScreen
  │   └── PurchaseDetailScreen
  ├── CustomerListScreen
  │   └── CustomerFormScreen
  ├── CompanyListScreen
  │   └── CompanyFormScreen
  ├── ExpenseListScreen
  │   └── ExpenseFormScreen
  └── SettingsScreen
      └── BusinessProfileScreen
```

---

## 7. Screen-by-Screen Specification

### 7.1 Home Screen

```
┌─────────────────────────────────────────────┐
│  KTS                            [bell] [search] │  header: app name left, icons right
│─────────────────────────────────────────────│
│                                             │
│  TODAY                     Wed, 3 Sep 2026  │  section label + date
│  ┌──────────────┬──────────────┐            │
│  │  Sales       │  Purchases   │            │  two equal-width summary cards
│  │  Rs 45,200   │  Rs 32,100   │            │  currency: large, mono font
│  │  12 bills    │  3 entries   │            │  count: caption, --text-secondary
│  └──────────────┴──────────────┘            │
│                                             │
│  QUICK ACTIONS                              │
│  ┌────────┐ ┌────────┐ ┌────────┐          │
│  │ Scan   │ │ Bill   │ │ Payment│          │  3 action tiles, 80px square
│  │ [cam]  │ │ [rcpt] │ │ [Rs]   │          │  icon 24px + label 12px
│  └────────┘ └────────┘ └────────┘          │  bg: --surface-secondary
│                                             │  radius: 10px
│  LOW STOCK                        View All  │
│  ┌─────────────────────────────────────────┐│
│  │  Mustard Oil          3 Cans   [ Low ] ││  compact list items
│  │──────────────────────────────────────────││  badge: status-warning
│  │  Wheat Flour          0 Bags   [ Out ] ││  badge: status-danger
│  │──────────────────────────────────────────││
│  │  Sugar                8 Bags   [ Low ] ││
│  └─────────────────────────────────────────┘│
│                                             │
│  OVERDUE PAYMENTS                 View All  │
│  ┌─────────────────────────────────────────┐│
│  │  Sharma Store     Rs 12,400    45 days  ││  name + amount + aging
│  │──────────────────────────────────────────││  aging text colored by bucket
│  │  Gupta Traders    Rs 8,200     32 days  ││
│  └─────────────────────────────────────────┘│
│                                             │
│  RECENT ACTIVITY                            │
│  ┌─────────────────────────────────────────┐│
│  │  Bill #INV-2026-0042                    ││  timeline list
│  │  Sharma Store  |  Rs 5,400  |  2:15 PM ││  each entry: type + party + amount + time
│  │──────────────────────────────────────────││
│  │  Purchase RF-2026-0881                  ││
│  │  Rajdhani Foods  |  Rs 51,275  |  11 AM ││
│  │──────────────────────────────────────────││
│  │  Payment Received                       ││
│  │  Gupta Traders  |  Rs 5,000  |  10 AM  ││
│  └─────────────────────────────────────────┘│
│                                             │
└─────────────────────────────────────────────┘
```

### 7.2 Stock Dashboard

```
┌─────────────────────────────────────────────┐
│  < Stock Dashboard              [filter]    │
│─────────────────────────────────────────────│
│  ┌─────────────────────────────────────────┐│
│  │ [search icon]  Search products...       ││  search bar: filled style
│  └─────────────────────────────────────────┘│
│                                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐      │  filter chips (horizontal scroll)
│  │ All  │ │ Low  │ │ Out  │ │ Oils │      │  active chip: --brand-primary bg
│  └──────┘ └──────┘ └──────┘ └──────┘      │  inactive: --surface-secondary
│                                             │
│  124 products                Sort: Stock ^  │  count + sort control
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │  Toor Dal Premium                  TDP  ││
│  │  250.0 Kg  (5 Bags)        Rs 22,500   ││  qty in both units + value
│  │  ████████████████████░░░░░             ││  stock bar: green fill
│  │──────────────────────────────────────────││
│  │  Mustard Oil                       MO   ││
│  │  45.0 L  (3 Cans)          Rs 6,300    ││
│  │  █████░░░░░░░░░░░░░░░░   [ Low ]      ││  bar: amber, badge shown
│  │──────────────────────────────────────────││
│  │  Wheat Flour Atta                  WFA  ││
│  │  0.0 Kg  (0 Bags)          Rs 0        ││
│  │  ░░░░░░░░░░░░░░░░░░░░░   [ Out ]      ││  bar: empty, red badge
│  │──────────────────────────────────────────││
│  │  Rice Basmati                      RB   ││
│  │  500.0 Kg  (20 Bags)      Rs 60,000    ││
│  │  ████████████████████████████████████   ││  bar: full green
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘

Stock bar specs:
  height: 4px
  radius: 2px
  bg: --border-default (track)
  fill: --status-success (>2x threshold)
        --status-warning (<=threshold, >0)
        --status-danger (0)
  No animation. Static fill.
```

### 7.3 New Bill Screen (Most Critical)

```
┌─────────────────────────────────────────────┐
│  < New Bill                        [clear]  │
│─────────────────────────────────────────────│
│                                             │
│  CUSTOMER                                   │
│  ┌─────────────────────────────────────────┐│
│  │ [search] Sharma General Store     [x]   ││  tap to open customer picker
│  └─────────────────────────────────────────┘│  selected: shows name + clear button
│                                             │
│  ITEMS                                      │
│  ┌─────────────────────────────────────────┐│
│  │  1.  Toor Dal Premium                   ││
│  │      2 Bag x Rs 5,500.00               ││  qty x rate
│  │      GST 5% (IGST)            Rs 550   ││  gst type + amount
│  │                            Rs 11,550.00 ││  line total: right-aligned, bold
│  │──────────────────────────────────────────││
│  │  2.  Mustard Oil                        ││
│  │      3 Can x Rs 2,550.00               ││
│  │      GST 5% (IGST)          Rs 382.50  ││
│  │                             Rs 8,032.50 ││
│  │──────────────────────────────────────────││
│  │  3.  Wheat Flour                        ││
│  │      5 Bag x Rs 350.00                 ││
│  │      GST 0%                     Rs 0    ││
│  │                             Rs 1,750.00 ││
│  └─────────────────────────────────────────┘│
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │  + Add Item                             ││  secondary button style
│  └─────────────────────────────────────────┘│  opens ItemPicker bottom sheet
│                                             │
│  ─────────────────────────────────────────  │  thin divider
│                                             │
│  Subtotal                      Rs 20,400.00 │  right-aligned mono font
│  IGST                           Rs 1,020.00 │  (or CGST+SGST if intra-state)
│  ─────────────────────────────────────────  │
│  TOTAL                        Rs 21,420.00  │  large, bold, --text-primary
│                                             │
│  PAYMENT                                    │
│  ┌──────┐ ┌──────┐ ┌──────┐               │  segmented control
│  │ Full │ │ Part │ │Credit│               │  active: --brand-primary bg, white text
│  └──────┘ └──────┘ └──────┘               │  inactive: --surface-secondary
│                                             │
│  (if Partial selected:)                     │
│  Amount Paid   ┌──────────────┐            │
│                │ Rs 10,000.00 │            │  number input
│                └──────────────┘            │
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │          Create Bill                    ││  primary button, full width
│  └─────────────────────────────────────────┘│  disabled if no customer or no items
│                                             │
└─────────────────────────────────────────────┘
```

### 7.4 Item Picker Bottom Sheet

```
┌─────────────────────────────────────────────┐
│  ────                                       │  drag handle
│  Add Item                            [X]    │
│─────────────────────────────────────────────│
│  ┌─────────────────────────────────────────┐│
│  │ [search]  Type product name or code     ││  auto-focus, search-as-you-type
│  └─────────────────────────────────────────┘│
│                                             │
│  RECENT (last 5 products billed)            │  section header
│  ┌─────────────────────────────────────────┐│
│  │  Toor Dal Premium     TDP    250 Kg     ││  name + code + available stock
│  │──────────────────────────────────────────││
│  │  Mustard Oil          MO     45 L       ││
│  └─────────────────────────────────────────┘│
│                                             │
│  ALL PRODUCTS                               │
│  ┌─────────────────────────────────────────┐│
│  │  Rice Basmati         RB     500 Kg     ││
│  │──────────────────────────────────────────││
│  │  Sugar                SG     80 Kg      ││
│  │──────────────────────────────────────────││
│  │  ...                                    ││  virtualized FlatList
│  └─────────────────────────────────────────┘│
│                                             │
│  (After selecting a product:)               │
│─────────────────────────────────────────────│
│  Toor Dal Premium                           │
│  Available: 250 Kg (5 Bags)                 │
│                                             │
│  Quantity      ┌────────┐  ┌─────┐         │
│                │ 2      │  │ Bag │         │  number input + unit selector
│                └────────┘  └─────┘         │
│  Rate          ┌────────────────┐          │
│                │ Rs 5,500.00    │          │  pre-filled from price tier
│                └────────────────┘          │
│  Discount      ┌────────┐                  │
│                │ 0 %     │                  │  optional
│                └────────┘                  │
│                                             │
│  Line Total                 Rs 11,000.00    │  calculated live
│  GST (5% IGST)                Rs 550.00     │
│  Net                        Rs 11,550.00    │
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │          Add to Bill                    ││  primary button
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

### 7.5 Bill Detail + PDF

```
┌─────────────────────────────────────────────┐
│  < Bill #INV-2026-0042                      │
│─────────────────────────────────────────────│
│                                             │
│  Sharma General Store            [ CREDIT ] │  customer name + status badge
│  3 Sep 2026                                 │  date below
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │  #  Item              Qty    Amount     ││  table header
│  │  ─────────────────────────────────────  ││
│  │  1  Toor Dal          2 Bag  11,550.00  ││
│  │  2  Mustard Oil       3 Can   8,032.50  ││
│  │  3  Wheat Flour       5 Bag   1,750.00  ││
│  │  ─────────────────────────────────────  ││
│  │  Subtotal                    20,400.00  ││
│  │  IGST                         1,020.00  ││
│  │  ─────────────────────────────────────  ││
│  │  Total                       21,420.00  ││  bold
│  │                                         ││
│  │  Paid                        10,000.00  ││
│  │  Balance Due                 11,420.00  ││  --status-danger color
│  └─────────────────────────────────────────┘│
│                                             │
│  ACTIONS                                    │
│  ┌────────────────┐  ┌────────────────┐    │
│  │  Download PDF  │  │  Share         │    │  two equal-width buttons
│  │  [pdf icon]    │  │  [share icon]  │    │  secondary button style
│  └────────────────┘  └────────────────┘    │
│  ┌────────────────┐  ┌────────────────┐    │
│  │  WhatsApp      │  │  Record        │    │
│  │  [wa icon]     │  │  Payment       │    │
│  └────────────────┘  └────────────────┘    │
│                                             │
│  LINKED LEDGER ENTRY                        │
│  ┌─────────────────────────────────────────┐│
│  │  Sale  |  Rs 21,420.00  |  3 Sep 2:15p ││  tappable: navigates to ledger
│  └─────────────────────────────────────────┘│
│                                             │
└─────────────────────────────────────────────┘
```

### 7.6 OCR Scan Flow

```
SCREEN 1: Camera
┌─────────────────────────────────────────────┐
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │                                         ││
│  │                                         ││
│  │          CAMERA VIEWFINDER              ││  full-screen camera
│  │                                         ││  document frame overlay (thin white border)
│  │          [ document frame ]             ││
│  │                                         ││
│  │                                         ││
│  └─────────────────────────────────────────┘│
│                                             │
│  Align the invoice within the frame         │  helper text
│                                             │
│  [Gallery]          [O]          [Flash]    │  bottom controls
│                   capture                   │  capture: 64px white circle
└─────────────────────────────────────────────┘


SCREEN 2: OCR Verify (State: CONFIRMING)
┌─────────────────────────────────────────────┐
│  < Review Purchase                          │
│─────────────────────────────────────────────│
│  ┌─────────────────────────────────────────┐│
│  │  Confidence: HIGH                       ││  confidence indicator bar
│  │  ████████████████████████████████████   ││  green bar, near-full
│  └─────────────────────────────────────────┘│
│                                             │
│  SUPPLIER                                   │
│  Rajdhani Foods Pvt Ltd          [matched]  │  "matched" in --status-success
│  Invoice: RF-2026-0881                      │
│  Date: 2026-09-03                           │
│                                             │
│  ITEMS (read-only, no editable fields)      │
│  ┌─────────────────────────────────────────┐│
│  │  1. Toor Dal        5 Bag   Rs 22,500  ││
│  │  2. Mustard Oil    10 Can   Rs 21,000  ││
│  │  3. Wheat Flour    20 Bag    Rs 5,600  ││
│  │  ─────────────────────────────────────  ││
│  │  GST (5%)                    Rs 2,175  ││
│  │  Total                      Rs 51,275  ││
│  └─────────────────────────────────────────┘│
│                                             │
│  Totals reconcile. Looks correct?           │
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │        Confirm and Save                 ││  primary button, green tint
│  └─────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────┐│
│  │        Edit Before Saving               ││  secondary button
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘


SCREEN 2b: OCR Verify (State: NEEDS FIX)
┌─────────────────────────────────────────────┐
│  < Review Purchase                          │
│─────────────────────────────────────────────│
│  ┌─────────────────────────────────────────┐│
│  │  Confidence: LOW — review flagged fields││  amber bar, partial fill
│  │  ██████████████░░░░░░░░░░░░░░░░░░░░░   ││
│  └─────────────────────────────────────────┘│
│                                             │
│  SUPPLIER                                   │
│  ┌─────────────────────────────────────────┐│
│  │  Rajdhani Foods Pvt Ltd     [matched]   ││
│  └─────────────────────────────────────────┘│
│                                             │
│  ITEMS (editable — flagged fields have      │
│  amber left border)                         │
│  ┌─────────────────────────────────────────┐│
│  │ ▌ 1. Toor Dal     [5]  Bag  [22,500]   ││  amber border on row = suspect
│  │   2. Mustard Oil  [10] Can  [21,000]    ││  normal row
│  │ ▌ 3. Wheat F???   [20] Bag  [5,600]    ││  amber: OCR couldn't read name
│  │   ─────────────────────────────────────  ││
│  │ ▌ Total                      [51,275]   ││  amber: total doesn't reconcile
│  └─────────────────────────────────────────┘│
│                                             │
│  Tap a flagged field to see the original    │
│  image region.                              │
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │        Confirm Corrections              ││  disabled until all flags resolved
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

### 7.7 Party Ledger

```
┌─────────────────────────────────────────────┐
│  < Sharma General Store                     │
│─────────────────────────────────────────────│
│                                             │
│  OUTSTANDING                                │
│  ┌─────────────────────────────────────────┐│
│  │              Rs 24,800.00               ││  large, center-aligned
│  │              ──────────────             ││  mono font, --status-danger color
│  │              Credit limit: Rs 50,000    ││  caption below
│  └─────────────────────────────────────────┘│
│                                             │
│  ┌────────────────┐  ┌────────────────┐    │
│  │ Record Payment │  │ Send Reminder  │    │
│  └────────────────┘  └────────────────┘    │
│                                             │
│  TRANSACTION HISTORY                        │
│  ┌─────────────────────────────────────────┐│
│  │  3 Sep 2026                             ││  date group header
│  │──────────────────────────────────────────││
│  │  Sale  Bill #INV-2026-0042              ││
│  │  +Rs 21,420.00         Bal: Rs 24,800   ││  amount + running balance
│  │──────────────────────────────────────────││
│  │  Payment (UPI)                          ││
│  │  -Rs 10,000.00         Bal: Rs 3,380    ││  payments are negative, green
│  │──────────────────────────────────────────││
│  │  2 Sep 2026                             ││
│  │──────────────────────────────────────────││
│  │  Sale  Bill #INV-2026-0041              ││
│  │  +Rs 13,380.00         Bal: Rs 13,380   ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘

Entry formatting:
  Sales (+):    --text-primary, amount right-aligned
  Payments (-): --status-success color
  Returns (-):  --status-warning color
  Running balance: --text-secondary, mono font, right edge
```

### 7.8 Outstanding Dashboard

```
┌─────────────────────────────────────────────┐
│  < Outstanding                              │
│─────────────────────────────────────────────│
│                                             │
│  ┌──────────────┬──────────────┐            │
│  │  Receivable  │  Payable     │            │
│  │ Rs 2,45,600  │ Rs 1,12,300  │            │  large mono
│  │ from customers│ to suppliers │            │  caption below
│  └──────────────┴──────────────┘            │
│                                             │
│  Net Position: Rs 1,33,300 receivable       │  single line summary
│                                             │
│  AGING BREAKDOWN                            │
│  ┌─────────────────────────────────────────┐│
│  │  0-30 days   ████████████   Rs 1,20,000 ││  horizontal bar
│  │  30-60 days  ██████         Rs 65,400   ││  each bar proportional
│  │  60-90 days  ████           Rs 40,200   ││  color: green/yellow/orange/red
│  │  90+ days    ██             Rs 20,000   ││
│  └─────────────────────────────────────────┘│
│                                             │
│  CUSTOMERS                    SUPPLIERS     │  segmented control
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │  Sharma Store      Rs 24,800    45d     ││
│  │  [phone]  [whatsapp]  [view ledger]     ││  inline action icons
│  │──────────────────────────────────────────││
│  │  Gupta Traders     Rs 18,200    32d     ││
│  │  [phone]  [whatsapp]  [view ledger]     ││
│  │──────────────────────────────────────────││
│  │  Patel Kirana      Rs 12,600    28d     ││
│  │  [phone]  [whatsapp]  [view ledger]     ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

### 7.9 Expense Form

```
┌─────────────────────────────────────────────┐
│  < Add Expense                              │
│─────────────────────────────────────────────│
│                                             │
│  CATEGORY                                   │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐      │  chip selector (wrap)
│  │ Fuel │ │Salary│ │ Rent │ │Trans.│      │  active: --brand-primary
│  └──────┘ └──────┘ └──────┘ └──────┘      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐      │
│  │ Pack │ │Elect.│ │Phone │ │ Misc │      │
│  └──────┘ └──────┘ └──────┘ └──────┘      │
│                                             │
│  Amount                                     │
│  ┌─────────────────────────────────────────┐│
│  │ Rs 2,500.00                             ││
│  └─────────────────────────────────────────┘│
│                                             │
│  Date                                       │
│  ┌─────────────────────────────────────────┐│
│  │ 3 Sep 2026                          [v] ││  date picker
│  └─────────────────────────────────────────┘│
│                                             │
│  Payment Mode                               │
│  ┌──────┐ ┌──────┐ ┌──────────┐            │
│  │ Cash │ │ UPI  │ │ Bank Txfr│            │  segmented control
│  └──────┘ └──────┘ └──────────┘            │
│                                             │
│  Note (optional)                            │
│  ┌─────────────────────────────────────────┐│
│  │ Delivery truck diesel — Rohtak route    ││  multiline text input
│  └─────────────────────────────────────────┘│
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │            Save Expense                 ││
│  └─────────────────────────────────────────┘│
└─────────────────────────────────────────────┘
```

---

## 8. Interaction Patterns

### Haptic Feedback
- Light tap: selecting a list item, toggling a chip
- Medium tap: confirming a bill, recording a payment
- No haptic on scroll, type, or navigation

### Loading States
- Skeleton screens for lists (not spinners)
- Inline button spinner (replace label with 20px spinner) for form submissions
- Pull-to-refresh on all list screens (standard Android pattern)

### Empty States
- No illustrations or mascots. Plain text + icon + action button.
```
  [Package icon, 32px, --text-tertiary]

  No products yet
  Add your first product to get started.

  [ + Add Product ]
```

### Destructive Actions
- Always require confirmation via a modal (not inline)
- Modal: "Delete this product?" with "Cancel" (left) and "Delete" (right, danger button)
- No swipe-to-delete (too easy to trigger accidentally with financial data)

### Form Validation
- Inline validation on blur (not on every keystroke)
- Error state: red border + red helper text below field
- Submit button disabled until all required fields are valid
- On submit error (API): toast with error message, form stays populated

### Keyboard
- Number inputs: open numeric keyboard
- Phone inputs: open phone keyboard
- Text inputs: default keyboard with autocorrect off for names/codes
- Auto-advance: after OTP digit entry, advance to next field

---

## 9. Animation & Motion

### Principles
- Functional, not decorative. Every animation communicates state change.
- Duration: 150-250ms for micro-interactions, 300ms for page transitions
- Easing: ease-out for entrances, ease-in for exits

### Specific Animations
```
Page transition:    Slide from right (stack push), slide to right (pop)
                    Duration: 250ms, ease-out
                    No opacity fade.

Bottom sheet:       Spring up from bottom
                    Duration: 200ms, damping: 0.85
                    Backdrop fades in simultaneously

Toast:              Slide up from bottom
                    Duration: 200ms
                    Auto-dismiss: slide down after 3s

List item:          No animation. Instant render.
                    (200+ item lists cannot afford per-item animation)

Tab switch:         Instant. No slide or fade between tab content.

Button press:       Scale to 0.97 on press, return to 1.0 on release
                    Duration: 100ms
                    Subtle opacity shift to 0.9

Pull to refresh:    Standard platform spinner (ActivityIndicator)
                    No custom animation
```

---

## 10. Responsive Considerations

### Screen Sizes
- **Minimum supported:** 320px width (older budget phones, 720p)
- **Design target:** 360-400px width (most common Android phones)
- **Maximum:** 430px width (large phones like Samsung Ultra)
- **No tablet layout** in v1 (not a target user device)

### Content Scaling
- All touch targets: minimum 44x44px
- Text never smaller than 12px
- Currency amounts never smaller than 13px
- Test all screens in: 360px, 400px, 320px widths

### Landscape
- Not supported. Lock to portrait orientation.
- Exception: camera capture screen (allow both)

---

## 11. Accessibility

### Minimum Requirements
- All interactive elements have `accessibilityLabel`
- Currency amounts read as "Rupees one thousand five hundred" not "Rs 1500"
- Status badges read as "Status: Paid" not just the color
- Minimum contrast: 4.5:1 for body text, 3:1 for large text
- No information conveyed by color alone (always paired with text/icon)

---

## 12. Performance Targets

| Metric | Target |
|:---|:---|
| App startup (cold) | < 2 seconds |
| Tab switch | < 100ms |
| Product search (10K products) | < 500ms |
| Bill creation (5 items) | < 30 seconds total |
| OCR scan to verify screen | < 10 seconds |
| PDF generation | < 3 seconds |
| List scroll | 60fps (no jank) |
| API response (cached) | < 100ms |
| API response (network) | < 2 seconds |

---

## 13. Tech Stack

| Layer | Technology |
|:---|:---|
| Framework | React Native (Expo managed) |
| Language | TypeScript (strict mode) |
| Navigation | React Navigation v6 (native stack) |
| State | Zustand (lightweight, no boilerplate) |
| API Client | Axios with interceptors (auth token, retry, error handling) |
| Forms | React Hook Form + Zod validation |
| Lists | FlashList (by Shopify — better perf than FlatList for large lists) |
| Camera | expo-camera + expo-image-picker |
| PDF | react-native-pdf (view) + backend API (generate) |
| Sharing | react-native-share (WhatsApp, email) |
| Storage | expo-secure-store (tokens), AsyncStorage (preferences) |
| Icons | phosphor-react-native |
| Fonts | expo-font (Inter, JetBrains Mono) |
| Crash reporting | Sentry |
| Analytics | Mixpanel (basic events only) |
