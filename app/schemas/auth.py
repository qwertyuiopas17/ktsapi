"""
KTS — Auth Schemas
Phone OTP flow + JWT + PIN setup.
"""
from pydantic import BaseModel, Field


class SendOtpRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15, description="Phone number with country code e.g. +919876543210")


class SendOtpResponse(BaseModel):
    message: str = "OTP sent successfully"
    session_id: str  # Firebase session ID for verification


class VerifyOtpRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    otp: str = Field(..., min_length=6, max_length=6)
    session_id: str


class VerifyOtpResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    is_new_user: bool
    has_business: bool


class SetPinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=6, pattern=r"^\d{4,6}$")


class VerifyPinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=6)


class BusinessSetupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    gstin: str | None = Field(None, max_length=15)
    state_code: str = Field(..., min_length=2, max_length=2, description="2-digit Indian state code")
    address: str | None = None
    phone: str | None = None
    upi_id: str | None = None
    bill_prefix: str = "INV"


class BusinessSetupResponse(BaseModel):
    business_id: str
    message: str = "Business created successfully"
