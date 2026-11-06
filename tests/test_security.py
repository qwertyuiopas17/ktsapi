"""Every non-auth, non-health route must require a bearer token."""
import re

from fastapi.routing import APIRoute

from app.main import app

PUBLIC = {
    ("POST", "/api/v1/auth/firebase"),
    ("POST", "/api/v1/auth/refresh"),
    ("GET", "/"),
    ("GET", "/health"),
}


def _routes():
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                yield method, route.path


def test_openapi_marks_every_private_route_as_bearer_protected():
    spec = app.openapi()
    missing = []
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if (method.upper(), path) in PUBLIC:
                continue
            if not any("HTTPBearer" in s for s in op.get("security", [])):
                missing.append(f"{method.upper()} {path}")
    assert not missing, f"Routes without bearer auth: {missing}"


def test_every_private_route_returns_401_without_token(client):
    failures = []
    for method, path in _routes():
        if (method, path) in PUBLIC:
            continue
        url = re.sub(r"\{party_type\}", "customer", path)
        url = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", url)
        r = client.request(method, url)
        if r.status_code != 401:
            failures.append(f"{method} {path} -> {r.status_code}")
    assert not failures, failures


def test_forged_token_rejected(client):
    import jwt

    forged = jwt.encode({"sub": "x", "type": "access"}, "wrong-secret", algorithm="HS256")
    r = client.get("/api/v1/products", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
