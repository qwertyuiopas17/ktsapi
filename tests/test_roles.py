from tests.conftest import bill, create_company, create_customer, create_product, make_staff, purchase


def _setup(owner):
    p = create_product(owner)
    c = create_company(owner)
    purchase(owner, c["id"], p["id"], 10, 100)
    cust = create_customer(owner)
    b = bill(owner, cust["id"], [{"product_id": p["id"], "quantity": 1, "unit": "Box", "rate": 150}])
    return p, c, cust, b


def test_delivery_role(client, owner):
    p, c, cust, b = _setup(owner)
    d = make_staff(client, owner, "delivery")
    assert d.get(f"/api/v1/bills/{b['id']}").status_code == 200
    assert d.get("/api/v1/customers").status_code == 200
    assert d.post("/api/v1/payments", json={"party_type": "customer", "party_id": cust["id"], "amount": 50}).status_code == 201
    assert d.post("/api/v1/payments", json={"party_type": "company", "party_id": c["id"], "amount": 50}).status_code == 403
    assert d.post("/api/v1/bills", json={"customer_id": cust["id"], "items": []}).status_code == 403
    assert d.get("/api/v1/purchases").status_code == 403
    assert d.get("/api/v1/dashboard").status_code == 403
    assert d.get(f"/api/v1/ledger/company/{c['id']}").status_code == 403


def test_warehouse_role(client, owner):
    p, c, cust, b = _setup(owner)
    w = make_staff(client, owner, "warehouse")
    assert w.get("/api/v1/inventory").status_code == 200
    assert w.get("/api/v1/products").status_code == 200
    r = w.post("/api/v1/inventory/adjustments", json={"reason": "damage", "items": [{"product_id": p["id"], "actual_qty": 8}]})
    assert r.status_code == 201
    assert w.get("/api/v1/bills").status_code == 403
    assert w.post("/api/v1/products", json={"name": "x"}).status_code == 403


def test_manager_cannot_delete_or_cancel(client, owner):
    p, c, cust, b = _setup(owner)
    m = make_staff(client, owner, "manager")
    assert m.post("/api/v1/customers", json={"name": "New"}).status_code == 201
    assert m.delete(f"/api/v1/products/{p['id']}").status_code == 403
    assert m.post(f"/api/v1/bills/{b['id']}/cancel", json={"reason": "nope"}).status_code == 403
    assert m.post("/api/v1/inventory/adjustments", json={"reason": "damage", "items": [{"product_id": p["id"], "actual_qty": 1}]}).status_code == 403


def test_accountant_cannot_manage_users_or_settings(client, owner):
    p, c, cust, b = _setup(owner)
    a = make_staff(client, owner, "accountant")
    assert a.post(f"/api/v1/bills/{b['id']}/cancel", json={"reason": "duplicate"}).status_code == 200
    assert a.get("/api/v1/users").status_code == 403
    assert a.put("/api/v1/auth/business", json={"name": "x", "state_code": "19"}).status_code == 403


def test_role_change_applies_immediately(client, owner):
    m = make_staff(client, owner, "manager")
    assert m.get("/api/v1/bills").status_code == 200
    owner.patch(f"/api/v1/users/{m.user_id}", json={"role": "warehouse"})
    assert m.get("/api/v1/bills").status_code == 403
