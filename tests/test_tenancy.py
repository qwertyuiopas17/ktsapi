"""
Tenant isolation: business B's owner must get 404 for every id-based route on
business A's resources. Routes are discovered from app.routes, so a new
endpoint with an unknown path parameter fails here until it is covered.
"""
import re

import pytest
from fastapi.routing import APIRoute

from app.main import app
from tests.conftest import (
    bill, create_company, create_customer, create_product, make_owner, make_staff, purchase,
)

# Minimal valid bodies so a 404 is not masked by a 422
BODIES = {
    ("PATCH", "/api/v1/products/{product_id}"): {"name": "x"},
    ("PATCH", "/api/v1/customers/{customer_id}"): {"name": "x"},
    ("PATCH", "/api/v1/companies/{company_id}"): {"name": "x"},
    ("PATCH", "/api/v1/users/{user_id}"): {"name": "x"},
    ("POST", "/api/v1/bills/{bill_id}/cancel"): {"reason": "tenant probe"},
}


@pytest.fixture
def world(client):
    a = make_owner(client, "Business A")
    b = make_owner(client, "Business B")
    product = create_product(a)
    customer = create_customer(a)
    company = create_company(a)
    purchase_resp = purchase(a, company["id"], product["id"], 10, 100)
    bill_resp = bill(a, customer["id"], [{"product_id": product["id"], "quantity": 1, "unit": "Box", "rate": 150}])
    expense = a.post("/api/v1/expenses", json={"category": "fuel", "amount": 500}).json()
    staff = make_staff(client, a, "manager")
    ids = {
        "product_id": product["id"],
        "customer_id": customer["id"],
        "company_id": company["id"],
        "purchase_id": purchase_resp["id"],
        "bill_id": bill_resp["id"],
        "expense_id": expense["id"],
        "user_id": staff.user_id,
    }
    return a, b, ids


def _id_routes():
    for route in app.routes:
        if isinstance(route, APIRoute) and "{" in route.path:
            for method in sorted(route.methods):
                yield method, route.path


def test_other_tenant_gets_404_on_every_id_route(world):
    a, b, ids = world
    failures = []
    checked = 0
    for method, path in _id_routes():
        params = re.findall(r"\{([^}]+)\}", path)
        variants = [{}]
        if "party_type" in params:
            variants = [
                {"party_type": "customer", "party_id": ids["customer_id"]},
                {"party_type": "company", "party_id": ids["company_id"]},
            ]
        for variant in variants:
            values = {**ids, **variant}
            unknown = [p for p in params if p not in values]
            assert not unknown, f"Add a fixture id for {unknown} used by {method} {path}"
            url = path.format(**values)
            body = BODIES.get((method, path))
            r = b.request(method, url, json=body) if body is not None else b.request(method, url)
            checked += 1
            if r.status_code != 404:
                failures.append(f"{method} {url} -> {r.status_code} {r.text[:120]}")
    assert checked >= 15
    assert not failures, "\n".join(failures)

    # And A still sees its own data
    assert a.get(f"/api/v1/bills/{ids['bill_id']}").status_code == 200


def test_lists_only_show_own_business(world):
    a, b, ids = world
    for url, key in [
        ("/api/v1/products", "products"), ("/api/v1/customers", "customers"),
        ("/api/v1/companies", "companies"), ("/api/v1/bills", "bills"),
        ("/api/v1/purchases", "purchases"), ("/api/v1/expenses", "expenses"),
        ("/api/v1/payments", "payments"),
    ]:
        assert b.get(url).json()[key] == [], url
    assert b.get("/api/v1/inventory").json()["items"] == []
    assert len(b.get("/api/v1/users").json()) == 1


def test_cannot_reference_other_tenant_ids_in_bodies(world):
    a, b, ids = world
    own_customer = create_customer(b)
    r = b.post("/api/v1/bills", json={
        "customer_id": own_customer["id"],
        "items": [{"product_id": ids["product_id"], "quantity": 1, "unit": "Box", "rate": 1}],
    })
    assert r.status_code == 404
    r = b.post("/api/v1/payments", json={"party_type": "customer", "party_id": ids["customer_id"], "amount": 10})
    assert r.status_code == 404
    r = b.post("/api/v1/inventory/adjustments", json={
        "reason": "stock_count", "items": [{"product_id": ids["product_id"], "actual_qty": 0}],
    })
    assert r.status_code == 404
