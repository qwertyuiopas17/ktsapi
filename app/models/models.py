"""
KTS — All Database Models
Complete schema from PRD §5 (v2), including OCR fields, cost-basis,
discount/damaged-qty, and per-supplier template references.

Every table uses UUID primary keys and timestamps.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    String, Text, Integer, Numeric, Boolean, Date, DateTime,
    Enum as SAEnum, ForeignKey, Index, UniqueConstraint, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# BUSINESS
# ---------------------------------------------------------------------------

class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(15))
    pan: Mapped[str | None] = mapped_column(String(10))
    address: Mapped[str | None] = mapped_column(Text)
    state_code: Mapped[str | None] = mapped_column(String(2))  # e.g. "27" for MH
    phone: Mapped[str | None] = mapped_column(String(15))
    email: Mapped[str | None] = mapped_column(String(255))
    upi_id: Mapped[str | None] = mapped_column(String(100))
    logo_url: Mapped[str | None] = mapped_column(Text)
    bill_prefix: Mapped[str] = mapped_column(String(10), default="INV")
    bill_counter: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    users = relationship("User", back_populates="business", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="business", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="business", cascade="all, delete-orphan")
    companies = relationship("Company", back_populates="business", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# USER
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum("owner", "manager", "delivery", "accountant", "warehouse",
               name="user_role"),
        default="owner",
    )
    pin_hash: Mapped[str | None] = mapped_column(String(255))  # bcrypt hash of 4-6 digit PIN
    firebase_uid: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now()

    # Relationships
    business = relationship("Business", back_populates="users")


# ---------------------------------------------------------------------------
# COMPANY (Suppliers)
# ---------------------------------------------------------------------------

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(15))
    phone: Mapped[str | None] = mapped_column(String(15))
    address: Mapped[str | None] = mapped_column(Text)
    state_code: Mapped[str | None] = mapped_column(String(2))
    contact_person: Mapped[str | None] = mapped_column(String(255))
    outstanding: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # OCR template learning — per-supplier layout reference
    ocr_template_id: Mapped[str | None] = mapped_column(String(255))
    ocr_trust_score: Mapped[int] = mapped_column(Integer, default=0)  # consecutive clean OCR bills
    ocr_graduated: Mapped[bool] = mapped_column(Boolean, default=False)  # auto-commit eligible

    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    business = relationship("Business", back_populates="companies")
    purchases = relationship("Purchase", back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_companies_business_name", "business_id", "name"),
    )


# ---------------------------------------------------------------------------
# CUSTOMER
# ---------------------------------------------------------------------------

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(15))
    address: Mapped[str | None] = mapped_column(Text)
    state_code: Mapped[str | None] = mapped_column(String(2))
    gstin: Mapped[str | None] = mapped_column(String(15))
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    outstanding: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    price_tier: Mapped[str] = mapped_column(
        SAEnum("retail", "wholesale", "special", name="price_tier"),
        default="retail",
    )
    beat_day: Mapped[str | None] = mapped_column(String(100))  # "Monday,Thursday"
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    business = relationship("Business", back_populates="customers")
    bills = relationship("Bill", back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_customers_business_name", "business_id", "name"),
        Index("ix_customers_business_phone", "business_id", "phone"),
    )


# ---------------------------------------------------------------------------
# PRODUCT
# ---------------------------------------------------------------------------

class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    shortcode: Mapped[str | None] = mapped_column(String(20))  # e.g. "TD" for Toor Dal
    hsn_code: Mapped[str | None] = mapped_column(String(8))
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)  # 0, 5, 18, 40
    category: Mapped[str | None] = mapped_column(String(100))

    # Units & conversion
    primary_unit: Mapped[str] = mapped_column(String(20), default="Piece")  # stocking unit
    secondary_unit: Mapped[str | None] = mapped_column(String(20))  # selling unit
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=1)

    # Pricing
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    sell_price_retail: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    sell_price_wholesale: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    sell_price_special: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    low_stock_threshold: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    is_loose_stock: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    business = relationship("Business", back_populates="products")
    inventory = relationship("Inventory", back_populates="product", uselist=False)

    __table_args__ = (
        Index("ix_products_business_name", "business_id", "name"),
        Index("ix_products_business_shortcode", "business_id", "shortcode"),
        Index("ix_products_business_hsn", "business_id", "hsn_code"),
    )


# ---------------------------------------------------------------------------
# INVENTORY (the product spine — always live)
# ---------------------------------------------------------------------------

class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id"), nullable=False, unique=True
    )
    qty_primary: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)  # in primary unit
    # qty_secondary is derived: qty_primary * conversion_factor — computed on read
    godown_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # Phase 2
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    product = relationship("Product", back_populates="inventory")
    transactions = relationship("InventoryTxn", back_populates="inventory", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_inventory_business", "business_id"),
    )


class InventoryTxn(Base):
    """Every stock movement is logged — the audit trail for inventory correctness."""
    __tablename__ = "inventory_txns"

    id: Mapped[uuid.UUID] = _uuid_pk()
    inventory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("inventory.id"), nullable=False
    )
    txn_type: Mapped[str] = mapped_column(
        SAEnum("purchase_in", "sale_out", "return_in", "return_out",
               "wastage", "adjustment", "transfer",
               name="inventory_txn_type"),
        nullable=False,
    )
    qty_change: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)  # +ve = in, -ve = out
    unit: Mapped[str] = mapped_column(String(20))
    reference_type: Mapped[str | None] = mapped_column(String(50))  # 'purchase', 'bill', 'adjustment'
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now()

    # Relationships
    inventory = relationship("Inventory", back_populates="transactions")

    __table_args__ = (
        Index("ix_invtxn_inventory_created", "inventory_id", "created_at"),
    )


# ---------------------------------------------------------------------------
# PURCHASE (inflow — the "front door" of the product)
# ---------------------------------------------------------------------------

class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("companies.id"), nullable=False
    )
    invoice_number: Mapped[str | None] = mapped_column(String(100))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    payment_status: Mapped[str] = mapped_column(
        SAEnum("paid", "partial", "credit", name="payment_status_type"),
        default="credit",
    )
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # OCR fields — PRD v2
    ocr_image_url: Mapped[str | None] = mapped_column(Text)  # retained original bill image
    source: Mapped[str] = mapped_column(
        SAEnum("ocr", "manual", name="purchase_source"), default="manual"
    )
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))  # 0.0000 – 1.0000
    verified_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))

    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now()

    # Relationships
    business = relationship("Business")
    company = relationship("Company", back_populates="purchases")
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_purchases_business_date", "business_id", "invoice_date"),
        Index("ix_purchases_company", "company_id"),
    )


class PurchaseItem(Base):
    """Line item on a purchase — captures discount & damaged qty for cost-basis."""
    __tablename__ = "purchase_items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    purchase_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("purchases.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(20))
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # v2 additions — cost-basis fields captured now, analytics computed in Phase 2
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    damaged_qty: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)  # not added to stock

    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Relationships
    purchase = relationship("Purchase", back_populates="items")
    product = relationship("Product")


# ---------------------------------------------------------------------------
# BILL (outflow — daily billing to customers)
# ---------------------------------------------------------------------------

class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customers.id"), nullable=False
    )
    bill_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    bill_type: Mapped[str] = mapped_column(
        SAEnum("invoice", "challan", "credit_note", name="bill_type"),
        default="invoice",
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    payment_status: Mapped[str] = mapped_column(
        SAEnum("paid", "partial", "credit", name="bill_payment_status"),
        default="credit",
    )
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    payment_mode: Mapped[str | None] = mapped_column(String(20))
    original_bill_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # for credit notes
    irn: Mapped[str | None] = mapped_column(String(100))  # e-invoice ref (Phase 2/3)

    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now()

    # Relationships
    business = relationship("Business")
    customer = relationship("Customer", back_populates="bills")
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_bills_business_date", "business_id", "bill_date"),
        Index("ix_bills_customer", "customer_id"),
    )


class BillItem(Base):
    __tablename__ = "bill_items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    bill_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bills.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(20))
    rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Cost-basis at time of sale — for Phase 2 margin analytics
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Relationships
    bill = relationship("Bill", back_populates="items")
    product = relationship("Product")


# ---------------------------------------------------------------------------
# PAYMENT
# ---------------------------------------------------------------------------

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id"), nullable=False
    )
    party_type: Mapped[str] = mapped_column(
        SAEnum("customer", "company", name="party_type"), nullable=False
    )
    party_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_mode: Mapped[str] = mapped_column(
        SAEnum("cash", "upi", "bank_transfer", "cheque", name="payment_mode_type"),
        default="cash",
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now()

    # Relationships
    business = relationship("Business")

    __table_args__ = (
        Index("ix_payments_party", "party_type", "party_id"),
        Index("ix_payments_business_date", "business_id", "payment_date"),
    )


# ---------------------------------------------------------------------------
# LEDGER ENTRY (auto-generated audit trail)
# ---------------------------------------------------------------------------

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id"), nullable=False
    )
    party_type: Mapped[str] = mapped_column(
        SAEnum("customer", "company", name="ledger_party_type"), nullable=False
    )
    party_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    entry_type: Mapped[str] = mapped_column(
        SAEnum("sale", "purchase", "payment_in", "payment_out",
               "return", "credit_note", "opening_balance",
               name="ledger_entry_type"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    running_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()

    # Relationships
    business = relationship("Business")

    __table_args__ = (
        Index("ix_ledger_party", "party_type", "party_id", "created_at"),
        Index("ix_ledger_business", "business_id"),
    )


# ---------------------------------------------------------------------------
# EXPENSE
# ---------------------------------------------------------------------------

class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(
        SAEnum("fuel", "salary", "rent", "transport", "packaging",
               "damage_waste", "electricity", "phone", "misc",
               name="expense_category"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_mode: Mapped[str] = mapped_column(
        SAEnum("cash", "upi", "bank_transfer", name="expense_payment_mode"),
        default="cash",
    )
    note: Mapped[str | None] = mapped_column(Text)
    receipt_url: Mapped[str | None] = mapped_column(Text)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now()

    # Relationships
    business = relationship("Business")

    __table_args__ = (
        Index("ix_expenses_business_date", "business_id", "expense_date"),
    )
