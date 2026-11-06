"""
KTS API — Karma Tattva Samiksha
"Examining the truth of every transaction."

Profit and claims tracking for multi-brand FMCG distributors: purchases (OCR),
inventory at moving-average cost, GST billing, party ledger and analytics.

The database schema is managed by Alembic — run `alembic upgrade head`.
"""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.logging_config import configure_logging, init_sentry
from app.rate_limit import limiter
from app.routers.auth import router as auth_router
from app.routers.bills import router as bills_router
from app.routers.dashboard import dashboard_router, inventory_router, ledger_router, payment_router
from app.routers.expenses import router as expenses_router
from app.routers.parties import company_router, customer_router
from app.routers.products import router as products_router
from app.routers.purchases import router as purchases_router
from app.routers.users import router as users_router
from app.services.inventory_service import InventoryError

configure_logging()
init_sentry()
log = logging.getLogger("kts.api")

app = FastAPI(
    title="KTS API",
    description=(
        "Karma Tattva Samiksha — distributor management API: OCR purchase capture, "
        "live inventory, GST billing, party ledger, and analytics."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    log.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 1),
        },
    )
    return response


@app.exception_handler(InventoryError)
async def inventory_error_handler(request: Request, exc: InventoryError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


for r in (
    auth_router, users_router, products_router, customer_router, company_router,
    purchases_router, bills_router, expenses_router, payment_router, ledger_router,
    inventory_router, dashboard_router,
):
    app.include_router(r)


@app.get("/", tags=["Health"])
@limiter.exempt
def root():
    return {"app": "KTS — Karma Tattva Samīkṣā", "version": app.version, "status": "running", "docs": "/docs"}


@app.get("/health", tags=["Health"])
@limiter.exempt
def health_check():
    return {"status": "ok"}
