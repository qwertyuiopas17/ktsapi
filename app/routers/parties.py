"""
KTS — Customer & Company Routers
CRUD for both parties (buyers + suppliers).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from decimal import Decimal
import uuid

from app.database import get_db
from app.models import Customer, Company
from app.schemas.entities import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse,
    CompanyCreate, CompanyUpdate, CompanyResponse, CompanyListResponse,
)


# ===========================================================================
# CUSTOMERS
# ===========================================================================

customer_router = APIRouter(prefix="/api/v1/customers", tags=["Customers"])


@customer_router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db)):
    """Add a new customer (kirana store / retailer)."""
    business_id = uuid.UUID("00000000-0000-0000-0000-000000000001")  # dev placeholder

    customer = Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        name=data.name,
        phone=data.phone,
        address=data.address,
        state_code=data.state_code,
        gstin=data.gstin,
        credit_limit=data.credit_limit,
        price_tier=data.price_tier,
        beat_day=data.beat_day,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@customer_router.get("", response_model=CustomerListResponse)
def list_customers(
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List customers with search and pagination."""
    business_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    query = db.query(Customer).filter(Customer.business_id == business_id)
    if search:
        term = f"%{search}%"
        query = query.filter(
            (Customer.name.ilike(term)) | (Customer.phone.ilike(term))
        )

    total = query.count()
    customers = query.order_by(Customer.name).offset(skip).limit(limit).all()

    return CustomerListResponse(
        customers=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
    )


@customer_router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


@customer_router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: uuid.UUID,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)

    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@customer_router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(customer)
    db.commit()


# ===========================================================================
# COMPANIES (Suppliers)
# ===========================================================================

company_router = APIRouter(prefix="/api/v1/companies", tags=["Companies"])


@company_router.post("", response_model=CompanyResponse, status_code=201)
def create_company(data: CompanyCreate, db: Session = Depends(get_db)):
    """Add a new supplier company."""
    business_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    company = Company(
        id=uuid.uuid4(),
        business_id=business_id,
        name=data.name,
        gstin=data.gstin,
        phone=data.phone,
        address=data.address,
        state_code=data.state_code,
        contact_person=data.contact_person,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return CompanyResponse.model_validate(company)


@company_router.get("", response_model=CompanyListResponse)
def list_companies(
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List supplier companies with search and pagination."""
    business_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    query = db.query(Company).filter(Company.business_id == business_id)
    if search:
        term = f"%{search}%"
        query = query.filter(Company.name.ilike(term))

    total = query.count()
    companies = query.order_by(Company.name).offset(skip).limit(limit).all()

    return CompanyListResponse(
        companies=[CompanyResponse.model_validate(c) for c in companies],
        total=total,
    )


@company_router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: uuid.UUID, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyResponse.model_validate(company)


@company_router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: uuid.UUID,
    data: CompanyUpdate,
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(company, key, value)

    db.commit()
    db.refresh(company)
    return CompanyResponse.model_validate(company)


@company_router.delete("/{company_id}", status_code=204)
def delete_company(company_id: uuid.UUID, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    db.delete(company)
    db.commit()
