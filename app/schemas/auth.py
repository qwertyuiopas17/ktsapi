"""
KTS — Auth Schemas
Firebase phone sign-in → KTS access + refresh tokens → PIN unlock → business setup.
"""
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["owner", "manager", "delivery", "accountant", "warehouse"]


class FirebaseLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=1, description="Firebase ID token from client-side Phone Auth")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: str
    business_id: str
    role: Role
    is_new_user: bool = False
    needs_business_setup: bool = False


class MeResponse(BaseModel):
    user_id: str
    name: str
    phone: str
    role: Role
    business_id: str
    business_name: str
    has_pin: bool
    needs_business_setup: bool


class SetPinRequest(BaseModel):
    pin: str = Field(..., pattern=r"^\d{4,6}$")


class VerifyPinRequest(BaseModel):
    pin: str = Field(..., pattern=r"^\d{4,6}$")


class VerifyPinResponse(BaseModel):
    valid: bool
    attempts_remaining: int


class BusinessSetupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    gstin: str | None = Field(None, max_length=15)
    state_code: str = Field(..., pattern=r"^\d{2}$", description="2-digit GST state code, e.g. 19 for West Bengal")
    address: str | None = None
    phone: str | None = None
    upi_id: str | None = None
    # Invoice numbers look like PREFIX/FY/NNNNN and must fit in 16 chars
    bill_prefix: str = Field("INV", pattern=r"^[A-Z0-9]{1,5}$")
    credit_policy: Literal["warn", "block"] = "block"


class BusinessSetupResponse(BaseModel):
    business_id: str
    message: str = "Business saved"


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., pattern=r"^\+\d{10,14}$")
    role: Role


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    role: Role | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: str
    name: str
    phone: str
    role: Role
    is_active: bool
