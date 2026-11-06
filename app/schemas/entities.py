"""
KTS — Product, Customer, Company Schemas
Pydantic models for CRUD + search endpoints.
"""
from typing import Literal

from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from uuid import UUID


# ---------------------------------------------------------------------------
# PRODUCT
# ---------------------------------------------------------------------------

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    shortcode: str | None = Field(None, max_length=20)
    hsn_code: str | None = Field(None, max_length=8)
    gst_rate: Decimal = Field(default=Decimal("0"), ge=0, le=40)
    category: str | None = None
    primary_unit: str = "Piece"
    secondary_unit: str | None = None
    conversion_factor: Decimal = Field(default=Decimal("1"), gt=0)
    purchase_price: Decimal = Field(default=Decimal("0"), ge=0)
    sell_price_retail: Decimal = Field(default=Decimal("0"), ge=0)
    sell_price_wholesale: Decimal = Field(default=Decimal("0"), ge=0)
    sell_price_special: Decimal = Field(default=Decimal("0"), ge=0)
    low_stock_threshold: Decimal = Field(default=Decimal("0"), ge=0)
    is_loose_stock: bool = False


class ProductUpdate(BaseModel):
    name: str | None = None
    shortcode: str | None = None
    hsn_code: str | None = None
    gst_rate: Decimal | None = Field(None, ge=0, le=40)
    category: str | None = None
    primary_unit: str | None = None
    secondary_unit: str | None = None
    conversion_factor: Decimal | None = Field(None, gt=0)
    purchase_price: Decimal | None = None
    sell_price_retail: Decimal | None = None
    sell_price_wholesale: Decimal | None = None
    sell_price_special: Decimal | None = None
    low_stock_threshold: Decimal | None = None
    is_loose_stock: bool | None = None


class ProductResponse(BaseModel):
    id: UUID
    name: str
    shortcode: str | None
    hsn_code: str | None
    gst_rate: Decimal
    category: str | None
    primary_unit: str
    secondary_unit: str | None
    conversion_factor: Decimal
    purchase_price: Decimal
    sell_price_retail: Decimal
    sell_price_wholesale: Decimal
    sell_price_special: Decimal
    low_stock_threshold: Decimal
    is_loose_stock: bool
    is_active: bool
    created_at: datetime

    # Stock info (joined from inventory)
    current_stock: Decimal | None = None
    avg_cost: Decimal | None = None  # moving-average cost per primary unit
    stock_value: Decimal | None = None

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    products: list[ProductResponse]
    total: int


# ---------------------------------------------------------------------------
# CUSTOMER
# ---------------------------------------------------------------------------

class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=15)
    address: str | None = None
    state_code: str | None = Field(None, max_length=2)
    gstin: str | None = Field(None, max_length=15)
    credit_limit: Decimal = Field(default=Decimal("0"), ge=0)
    price_tier: Literal["retail", "wholesale", "special"] = "retail"
    beat_day: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    state_code: str | None = None
    gstin: str | None = None
    credit_limit: Decimal | None = Field(None, ge=0)
    price_tier: Literal["retail", "wholesale", "special"] | None = None
    beat_day: str | None = None


class CustomerResponse(BaseModel):
    id: UUID
    name: str
    phone: str | None
    address: str | None
    state_code: str | None
    gstin: str | None
    credit_limit: Decimal
    outstanding: Decimal
    price_tier: str
    beat_day: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    customers: list[CustomerResponse]
    total: int


# ---------------------------------------------------------------------------
# COMPANY (Supplier)
# ---------------------------------------------------------------------------

class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    gstin: str | None = Field(None, max_length=15)
    phone: str | None = Field(None, max_length=15)
    address: str | None = None
    state_code: str | None = Field(None, max_length=2)
    contact_person: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    gstin: str | None = None
    phone: str | None = None
    address: str | None = None
    state_code: str | None = None
    contact_person: str | None = None


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    gstin: str | None
    phone: str | None
    address: str | None
    state_code: str | None
    contact_person: str | None
    outstanding: Decimal
    ocr_graduated: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    companies: list[CompanyResponse]
    total: int


# ---------------------------------------------------------------------------
# GST Lookup
# ---------------------------------------------------------------------------

class HsnLookupResponse(BaseModel):
    hsn_code: str
    gst_rate: Decimal | None
    cess_rate: Decimal | None = None
    description: str | None = None
    note: str | None = None
    requires_ca_review: bool = False
