"""
KTS — Purchase, Bill, Payment, Inventory Schemas
The transactional core — every one of these mutations moves stock, updates ledger, or both.
"""
from typing import Literal

from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID


# ---------------------------------------------------------------------------
# PURCHASE (inflow)
# ---------------------------------------------------------------------------

class PurchaseItemCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0)
    unit: str
    rate: Decimal = Field(..., ge=0)
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    damaged_qty: Decimal = Field(default=Decimal("0"), ge=0)
    gst_rate: Decimal = Field(default=Decimal("0"), ge=0)


class PurchaseCreate(BaseModel):
    company_id: UUID
    invoice_number: str | None = None
    invoice_date: date | None = None
    items: list[PurchaseItemCreate] = Field(..., min_length=1)
    payment_status: Literal["paid", "partial", "credit"] = "credit"
    amount_paid: Decimal = Field(default=Decimal("0"), ge=0)
    ocr_image_url: str | None = None
    source: Literal["manual", "ocr"] = "manual"


class PurchaseItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str | None = None
    quantity: Decimal
    unit: str
    rate: Decimal
    discount_pct: Decimal
    discount_amount: Decimal
    damaged_qty: Decimal
    gst_rate: Decimal
    gst_amount: Decimal
    total: Decimal
    model_config = {"from_attributes": True}


class PurchaseResponse(BaseModel):
    id: UUID
    company_id: UUID
    company_name: str | None = None
    invoice_number: str | None
    invoice_date: date | None
    subtotal: Decimal
    gst_amount: Decimal
    total_amount: Decimal
    payment_status: str
    amount_paid: Decimal
    source: str
    ocr_image_url: str | None
    ocr_confidence: Decimal | None
    items: list[PurchaseItemResponse] = []
    created_at: datetime
    model_config = {"from_attributes": True}


class PurchaseListResponse(BaseModel):
    purchases: list[PurchaseResponse]
    total: int


# ---------------------------------------------------------------------------
# BILL (outflow)
# ---------------------------------------------------------------------------

class BillItemCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0)
    unit: str
    rate: Decimal = Field(..., ge=0)
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class BillCreate(BaseModel):
    customer_id: UUID
    bill_date: date | None = None  # defaults to today
    # Credit notes need their own flow (stock back in, not out) and arrive in Phase 3
    bill_type: Literal["invoice", "challan"] = "invoice"
    items: list[BillItemCreate] = Field(..., min_length=1)
    payment_status: Literal["paid", "partial", "credit"] = "credit"
    amount_paid: Decimal = Field(default=Decimal("0"), ge=0)
    payment_mode: str | None = None  # cash, upi, bank_transfer


class BillItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str | None = None
    quantity: Decimal
    unit: str
    rate: Decimal
    discount_pct: Decimal
    gst_rate: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    total: Decimal
    cost_basis: Decimal
    model_config = {"from_attributes": True}


class BillResponse(BaseModel):
    id: UUID
    customer_id: UUID
    customer_name: str | None = None
    bill_number: str
    bill_date: date
    bill_type: str
    subtotal: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    round_off: Decimal = Decimal("0")
    total_amount: Decimal
    status: str = "active"
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    payment_status: str
    amount_paid: Decimal
    payment_mode: str | None
    items: list[BillItemResponse] = []
    created_at: datetime
    warnings: list[str] = []
    model_config = {"from_attributes": True}


class BillCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class BillListResponse(BaseModel):
    bills: list[BillResponse]
    total: int


# ---------------------------------------------------------------------------
# PAYMENT
# ---------------------------------------------------------------------------

class PaymentCreate(BaseModel):
    party_type: Literal["customer", "company"]
    party_id: UUID
    amount: Decimal = Field(..., gt=0)
    payment_mode: Literal["cash", "upi", "bank_transfer", "cheque"] = "cash"
    payment_date: date | None = None
    reference: str | None = None
    note: str | None = None


class PaymentResponse(BaseModel):
    id: UUID
    party_type: str
    party_id: UUID
    party_name: str | None = None
    amount: Decimal
    payment_mode: str
    payment_date: date
    reference: str | None
    note: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    payments: list[PaymentResponse]
    total: int


# ---------------------------------------------------------------------------
# INVENTORY
# ---------------------------------------------------------------------------

class StockItem(BaseModel):
    product_id: UUID
    product_name: str
    shortcode: str | None
    category: str | None
    qty_primary: Decimal
    qty_secondary: Decimal
    primary_unit: str
    secondary_unit: str | None
    stock_value: Decimal
    low_stock_threshold: Decimal
    status: str  # ok, low, out
    last_purchase_date: date | None = None


class StockDashboardResponse(BaseModel):
    items: list[StockItem]
    total_items: int
    total_value: Decimal
    low_stock_count: int
    out_of_stock_count: int


AdjustReason = Literal["stock_count", "damage", "expiry", "theft", "measurement_error", "personal_use", "opening_stock"]


class StockAdjustRequest(BaseModel):
    product_id: UUID
    actual_qty: Decimal = Field(..., ge=0, description="Counted quantity in the primary unit")
    reason: AdjustReason


class StockCountLine(BaseModel):
    product_id: UUID
    actual_qty: Decimal = Field(..., ge=0, description="Counted quantity in the primary unit")
    unit_cost: Decimal | None = Field(None, ge=0, description="Only for opening_stock: cost per primary unit")


class StockAdjustmentBatch(BaseModel):
    reason: AdjustReason
    note: str | None = Field(None, max_length=500)
    items: list[StockCountLine] = Field(..., min_length=1, max_length=500)


class StockAdjustmentLineResult(BaseModel):
    product_id: UUID
    product_name: str
    previous_qty: Decimal
    actual_qty: Decimal
    difference: Decimal


class StockAdjustmentBatchResponse(BaseModel):
    adjustment_id: UUID
    reason: str
    items: list[StockAdjustmentLineResult]


class InventoryTxnResponse(BaseModel):
    id: UUID
    txn_type: str
    qty_change: Decimal
    unit_cost: Decimal | None = None
    unit: str | None
    reference_type: str | None
    note: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# LEDGER
# ---------------------------------------------------------------------------

class LedgerEntryResponse(BaseModel):
    id: UUID
    entry_type: str
    amount: Decimal
    running_balance: Decimal
    reference_type: str | None
    description: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class PartyLedgerResponse(BaseModel):
    party_type: str
    party_id: UUID
    party_name: str
    outstanding: Decimal
    entries: list[LedgerEntryResponse]


class OutstandingResponse(BaseModel):
    total_receivable: Decimal  # from customers
    total_payable: Decimal     # to suppliers
    net_position: Decimal
    top_overdue_customers: list[dict] = []


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

class DashboardResponse(BaseModel):
    today_sales: Decimal
    today_purchases: Decimal
    today_expenses: Decimal
    low_stock_count: int
    overdue_count: int
    recent_activity: list[dict] = []


# ---------------------------------------------------------------------------
# EXPENSE
# ---------------------------------------------------------------------------

class ExpenseCreate(BaseModel):
    category: str = Field(..., description="fuel|salary|rent|transport|packaging|damage_waste|electricity|phone|misc")
    amount: Decimal = Field(..., gt=0)
    expense_date: date | None = None
    payment_mode: str = "cash"  # cash, upi, bank_transfer
    note: str | None = None
    receipt_url: str | None = None
    is_recurring: bool = False


class ExpenseResponse(BaseModel):
    id: UUID
    category: str
    amount: Decimal
    expense_date: date
    payment_mode: str
    note: str | None
    receipt_url: str | None
    is_recurring: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ExpenseListResponse(BaseModel):
    expenses: list[ExpenseResponse]
    total: int
    total_amount: Decimal = Decimal("0")


class ExpenseSummaryResponse(BaseModel):
    """Category-wise expense breakdown for a date range."""
    period_start: date
    period_end: date
    total: Decimal
    by_category: dict[str, Decimal] = {}

