"""
Shared fixtures. Set TEST_DATABASE_URL to run against Postgres (CI does);
otherwise a throwaway SQLite file is used for quick local runs.
"""
import os
import tempfile
import uuid
from pathlib import Path

_sqlite_path = Path(tempfile.gettempdir()) / f"kts_test_{os.getpid()}.db"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_sqlite_path}")
os.environ["APP_ENV"] = "test"
os.environ["AUTH_DEV_STUB"] = "true"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["LOG_JSON"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-123456"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IS_POSTGRES = engine.dialect.name == "postgresql"


def alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    """Build the schema exactly the way production does: through Alembic."""
    if not IS_POSTGRES and _sqlite_path.exists():
        _sqlite_path.unlink()
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    engine.dispose()
    if not IS_POSTGRES and _sqlite_path.exists():
        _sqlite_path.unlink()


@pytest.fixture(autouse=True)
def clean_tables(migrated_db):
    yield
    with engine.begin() as conn:
        if IS_POSTGRES:
            names = ", ".join(t.name for t in Base.metadata.sorted_tables)
            conn.execute(text(f"TRUNCATE {names} CASCADE"))
        else:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture
def client():
    return TestClient(app)


def random_phone() -> str:
    return "+91" + str(uuid.uuid4().int)[:10].rjust(10, "9")


class Actor:
    """A signed-in user with helpers for authenticated calls."""

    def __init__(self, client: TestClient, tokens: dict):
        self.client = client
        self.tokens = tokens
        self.user_id = tokens["user_id"]
        self.business_id = tokens["business_id"]

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def request(self, method: str, url: str, **kw):
        return self.client.request(method, url, headers=self.headers, **kw)

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)

    def patch(self, url, **kw):
        return self.request("PATCH", url, **kw)

    def put(self, url, **kw):
        return self.request("PUT", url, **kw)

    def delete(self, url, **kw):
        return self.request("DELETE", url, **kw)


def login(client: TestClient, phone: str) -> Actor:
    r = client.post("/api/v1/auth/firebase", json={"id_token": f"dev:{phone}"})
    assert r.status_code == 200, r.text
    return Actor(client, r.json())


def make_owner(client: TestClient, name: str = "Biz", state_code: str = "19", **business) -> Actor:
    owner = login(client, random_phone())
    r = owner.put("/api/v1/auth/business", json={"name": name, "state_code": state_code, **business})
    assert r.status_code == 200, r.text
    return owner


def make_staff(client: TestClient, owner: Actor, role: str) -> Actor:
    phone = random_phone()
    r = owner.post("/api/v1/users", json={"name": f"{role} user", "phone": phone, "role": role})
    assert r.status_code == 201, r.text
    return login(client, phone)


@pytest.fixture
def owner(client) -> Actor:
    return make_owner(client, "Kolkata Traders")


# ─── master-data helpers ────────────────────────────────────
def create_product(actor: Actor, **over) -> dict:
    body = {
        "name": over.pop("name", f"Product {uuid.uuid4().hex[:6]}"),
        "hsn_code": "3401", "gst_rate": 5, "primary_unit": "Box", "secondary_unit": "Piece",
        "conversion_factor": 10, "sell_price_wholesale": 30,
    }
    body.update(over)
    r = actor.post("/api/v1/products", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def create_customer(actor: Actor, **over) -> dict:
    body = {"name": f"Store {uuid.uuid4().hex[:6]}", "state_code": "19", "phone": "+919800000001"}
    body.update(over)
    r = actor.post("/api/v1/customers", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def create_company(actor: Actor, **over) -> dict:
    body = {"name": f"Brand {uuid.uuid4().hex[:6]}", "state_code": "19"}
    body.update(over)
    r = actor.post("/api/v1/companies", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def purchase(actor: Actor, company_id: str, product_id: str, qty, rate, unit="Box", **item) -> dict:
    r = actor.post("/api/v1/purchases", json={
        "company_id": company_id,
        "invoice_number": f"P-{uuid.uuid4().hex[:6]}",
        "items": [{"product_id": product_id, "quantity": qty, "unit": unit, "rate": rate, **item}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def bill(actor: Actor, customer_id: str, items: list[dict], expect: int = 201, **over):
    body = {"customer_id": customer_id, "items": items, "bill_date": "2026-05-10"}
    body.update(over)
    r = actor.post("/api/v1/bills", json=body)
    assert r.status_code == expect, r.text
    return r.json()
