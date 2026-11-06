"""
KTS — Customer & Company Routers
CRUD for both parties (buyers + suppliers), scoped to the caller's business.
Parties with financial history cannot be hard-deleted.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import ADMIN, FIELD, OPS, RequestContext, allow
from app.models import Bill, Company, Customer, LedgerEntry, Payment, Purchase
from app.schemas.entities import (
    CompanyCreate, CompanyListResponse, CompanyResponse, CompanyUpdate,
    CustomerCreate, CustomerListResponse, CustomerResponse, CustomerUpdate,
)
from app.utils.scoping import get_owned


def _has_history(db: Session, party_type: str, party_id: uuid.UUID, business_id: uuid.UUID) -> bool:
    doc = Bill if party_type == "customer" else Purchase
    doc_fk = Bill.customer_id if party_type == "customer" else Purchase.company_id
    if db.query(doc.id).filter(doc_fk == party_id, doc.business_id == business_id).first():
        return True
    for model in (LedgerEntry, Payment):
        if db.query(model.id).filter(
            model.party_type == party_type, model.party_id == party_id, model.business_id == business_id
        ).first():
            return True
    return False


# ===========================================================================
# CUSTOMERS
# ===========================================================================

customer_router = APIRouter(prefix="/api/v1/customers", tags=["Customers"])


@customer_router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(data: CustomerCreate, ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    """Add a new customer (kirana store / retailer)."""
    customer = Customer(id=uuid.uuid4(), business_id=ctx.business_id, **data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@customer_router.get("", response_model=CustomerListResponse)
def list_customers(
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: RequestContext = Depends(allow(*FIELD)),
    db: Session = Depends(get_db),
):
    """List customers with search and pagination."""
    query = db.query(Customer).filter(Customer.business_id == ctx.business_id)
    if search:
        term = f"%{search}%"
        query = query.filter((Customer.name.ilike(term)) | (Customer.phone.ilike(term)))

    total = query.count()
    customers = query.order_by(Customer.name).offset(skip).limit(limit).all()
    return CustomerListResponse(
        customers=[CustomerResponse.model_validate(c) for c in customers], total=total
    )


@customer_router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: uuid.UUID, ctx: RequestContext = Depends(allow(*FIELD)), db: Session = Depends(get_db)):
    return CustomerResponse.model_validate(get_owned(db, Customer, customer_id, ctx, detail="Customer not found"))


@customer_router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: uuid.UUID,
    data: CustomerUpdate,
    ctx: RequestContext = Depends(allow(*OPS)),
    db: Session = Depends(get_db),
):
    customer = get_owned(db, Customer, customer_id, ctx, detail="Customer not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)


@customer_router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: uuid.UUID, ctx: RequestContext = Depends(allow(*ADMIN)), db: Session = Depends(get_db)):
    customer = get_owned(db, Customer, customer_id, ctx, detail="Customer not found")
    if _has_history(db, "customer", customer.id, ctx.business_id):
        raise HTTPException(status_code=409, detail="Customer has bills or ledger history and cannot be deleted")
    db.delete(customer)
    db.commit()


# ===========================================================================
# COMPANIES (Suppliers)
# ===========================================================================

company_router = APIRouter(prefix="/api/v1/companies", tags=["Companies"])


@company_router.post("", response_model=CompanyResponse, status_code=201)
def create_company(data: CompanyCreate, ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    """Add a new supplier company."""
    company = Company(id=uuid.uuid4(), business_id=ctx.business_id, **data.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return CompanyResponse.model_validate(company)


@company_router.get("", response_model=CompanyListResponse)
def list_companies(
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: RequestContext = Depends(allow(*OPS)),
    db: Session = Depends(get_db),
):
    """List supplier companies with search and pagination."""
    query = db.query(Company).filter(Company.business_id == ctx.business_id)
    if search:
        term = f"%{search}%"
        query = query.filter((Company.name.ilike(term)) | (Company.gstin.ilike(term)))

    total = query.count()
    companies = query.order_by(Company.name).offset(skip).limit(limit).all()
    return CompanyListResponse(
        companies=[CompanyResponse.model_validate(c) for c in companies], total=total
    )


@company_router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: uuid.UUID, ctx: RequestContext = Depends(allow(*OPS)), db: Session = Depends(get_db)):
    return CompanyResponse.model_validate(get_owned(db, Company, company_id, ctx, detail="Company not found"))


@company_router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: uuid.UUID,
    data: CompanyUpdate,
    ctx: RequestContext = Depends(allow(*OPS)),
    db: Session = Depends(get_db),
):
    company = get_owned(db, Company, company_id, ctx, detail="Company not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(company, key, value)
    db.commit()
    db.refresh(company)
    return CompanyResponse.model_validate(company)


@company_router.delete("/{company_id}", status_code=204)
def delete_company(company_id: uuid.UUID, ctx: RequestContext = Depends(allow(*ADMIN)), db: Session = Depends(get_db)):
    company = get_owned(db, Company, company_id, ctx, detail="Company not found")
    if _has_history(db, "company", company.id, ctx.business_id):
        raise HTTPException(status_code=409, detail="Company has purchases or ledger history and cannot be deleted")
    db.delete(company)
    db.commit()
