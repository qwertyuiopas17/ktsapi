"""Row-lock behaviour. Needs Postgres (SQLite ignores SELECT ... FOR UPDATE)."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import IS_POSTGRES, create_company, create_customer, create_product, purchase

pytestmark = pytest.mark.skipif(not IS_POSTGRES, reason="row locks need Postgres; set TEST_DATABASE_URL")


def _post_bill(headers, customer_id, product_id):
    with TestClient(app) as c:
        return c.post("/api/v1/bills", headers=headers, json={
            "customer_id": customer_id, "bill_date": "2026-05-10",
            "items": [{"product_id": product_id, "quantity": 1, "unit": "Box", "rate": 10}],
        })


def test_last_unit_sold_once(owner):
    p = create_product(owner)
    c = create_company(owner)
    purchase(owner, c["id"], p["id"], 1, 5)
    cust = create_customer(owner)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: _post_bill(owner.headers, cust["id"], p["id"]), range(2)))
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 400], [r.text for r in results]
    assert owner.get(f"/api/v1/products/{p['id']}").json()["current_stock"] in ("0", "0.0000")


def test_50_concurrent_bills_get_unique_gap_free_numbers(owner):
    p = create_product(owner)
    c = create_company(owner)
    purchase(owner, c["id"], p["id"], 100, 5)
    cust = create_customer(owner)
    with ThreadPoolExecutor(10) as pool:
        results = list(pool.map(lambda _: _post_bill(owner.headers, cust["id"], p["id"]), range(50)))
    assert all(r.status_code == 201 for r in results), [r.text for r in results if r.status_code != 201][:3]
    numbers = sorted(r.json()["bill_number"] for r in results)
    assert numbers == [f"INV/2627/{n:05d}" for n in range(1, 51)]
