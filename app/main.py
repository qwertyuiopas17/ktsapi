"""
KTS API — Karma Tattva Samiksha
"Examining the truth of every transaction."

All-in-one distributor management backend: purchases (OCR), inventory,
billing, ledger, GST compliance, and analytics.
"""
# UTF-8 fix for Windows console (ported from aethel-backend-v3/main.py)
import sys
import io
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base
from app.routers.auth import router as auth_router
from app.routers.products import router as products_router
from app.routers.parties import customer_router, company_router
from app.routers.purchases import router as purchases_router
from app.routers.bills import router as bills_router
from app.routers.expenses import router as expenses_router
from app.routers.dashboard import (
    payment_router, ledger_router, inventory_router, dashboard_router,
)

# ---------------------------------------------------------------------------
# Create tables (development only — use Alembic migrations in production)
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="KTS API",
    description=(
        "Karma Tattva Samiksha - All-in-one distributor management API: "
        "OCR purchase capture, live inventory, GST billing, party ledger, and analytics."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow mobile app and web dashboard origins
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(customer_router)
app.include_router(company_router)
app.include_router(purchases_router)
app.include_router(bills_router)
app.include_router(expenses_router)
app.include_router(payment_router)
app.include_router(ledger_router)
app.include_router(inventory_router)
app.include_router(dashboard_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/", tags=["Health"])
def root():
    return {
        "app": "KTS — Karma Tattva Samīkṣā",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
