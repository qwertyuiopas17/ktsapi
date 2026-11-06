from app.config import settings
from app.rate_limit import limiter
from tests.conftest import login, make_owner, make_staff, random_phone


def test_first_login_creates_owner_and_business(client):
    r = client.post("/api/v1/auth/firebase", json={"id_token": f"dev:{random_phone()}"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "owner"
    assert body["is_new_user"] is True
    assert body["needs_business_setup"] is True
    assert body["refresh_token"] and body["access_token"]


def test_second_login_returns_same_user(client):
    phone = random_phone()
    first = login(client, phone)
    again = login(client, phone)
    assert again.user_id == first.user_id
    assert again.tokens["is_new_user"] is False


def test_invalid_identity_token_rejected(client):
    assert client.post("/api/v1/auth/firebase", json={"id_token": "dev:not-a-phone"}).status_code == 401
    # 401 when firebase-admin is installed; 503 ("not configured") where it is not
    assert client.post("/api/v1/auth/firebase", json={"id_token": "garbage"}).status_code in (401, 503)


def test_business_setup_and_me(client):
    owner = make_owner(client, "Howrah Distributors", gstin="19AAACH1234F1Z5", bill_prefix="HD")
    me = owner.get("/api/v1/auth/me").json()
    assert me["business_name"] == "Howrah Distributors"
    assert me["needs_business_setup"] is False
    assert me["has_pin"] is False


def test_bill_prefix_must_fit_gst_length(client):
    owner = login(client, random_phone())
    r = owner.put("/api/v1/auth/business", json={"name": "X", "state_code": "19", "bill_prefix": "TOOLONG"})
    assert r.status_code == 422


def test_refresh_rotation_and_reuse_detection(client):
    owner = make_owner(client)
    old_refresh = owner.tokens["refresh_token"]

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    new = r.json()
    assert new["refresh_token"] != old_refresh

    # Re-using the rotated token is treated as theft: every session dies
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}).status_code == 401
    headers = {"Authorization": f"Bearer {new['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_logout_revokes_refresh_token(client):
    owner = make_owner(client)
    assert owner.post("/api/v1/auth/logout", json={"refresh_token": owner.tokens["refresh_token"]}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": owner.tokens["refresh_token"]}).status_code == 401
    # The access token keeps working until it expires
    assert owner.get("/api/v1/auth/me").status_code == 200


def test_logout_all_revokes_access_tokens(client):
    owner = make_owner(client)
    assert owner.post("/api/v1/auth/logout-all").status_code == 204
    assert owner.get("/api/v1/auth/me").status_code == 401


def test_pin_set_verify_and_lockout(client):
    owner = make_owner(client)
    assert owner.post("/api/v1/auth/set-pin", json={"pin": "4821"}).status_code == 204
    ok = owner.post("/api/v1/auth/verify-pin", json={"pin": "4821"}).json()
    assert ok["valid"] is True

    for _ in range(settings.PIN_MAX_ATTEMPTS - 1):
        r = owner.post("/api/v1/auth/verify-pin", json={"pin": "0000"})
        assert r.status_code == 200 and r.json()["valid"] is False
    r = owner.post("/api/v1/auth/verify-pin", json={"pin": "0000"})
    assert r.status_code == 401
    assert owner.get("/api/v1/auth/me").status_code == 401


def test_invited_staff_signs_in_with_role(client):
    owner = make_owner(client)
    staff = make_staff(client, owner, "delivery")
    assert staff.tokens["role"] == "delivery"
    assert staff.business_id == owner.business_id


def test_disabled_user_loses_access(client):
    owner = make_owner(client)
    staff = make_staff(client, owner, "manager")
    assert owner.patch(f"/api/v1/users/{staff.user_id}", json={"is_active": False}).status_code == 200
    assert staff.get("/api/v1/auth/me").status_code == 401
    phone = next(u["phone"] for u in owner.get("/api/v1/users").json() if u["id"] == staff.user_id)
    r = client.post("/api/v1/auth/firebase", json={"id_token": f"dev:{phone}"})
    assert r.status_code == 403


def test_owner_cannot_demote_self(client):
    owner = make_owner(client)
    assert owner.patch(f"/api/v1/users/{owner.user_id}", json={"role": "manager"}).status_code == 400


def test_auth_rate_limit(client):
    limiter.enabled = True
    limiter.reset()
    try:
        limit = int(settings.RATE_LIMIT_AUTH.split("/")[0])
        codes = [
            client.post("/api/v1/auth/firebase", json={"id_token": "dev:bad"}).status_code
            for _ in range(limit + 1)
        ]
        assert codes[-1] == 429
        assert 429 not in codes[:limit]
    finally:
        limiter.enabled = False
        limiter.reset()
