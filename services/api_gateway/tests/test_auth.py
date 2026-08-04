"""API gateway auth tests."""

import pytest
from fastapi.testclient import TestClient

from api_gateway.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["execution_mode"] == "paper"


def test_login_admin_and_me(client: TestClient) -> None:
    res = client.post(
        "/v1/auth/login",
        data={"username": "admin@local.dev", "password": "ChangeMeAdmin123!"},
    )
    assert res.status_code == 200
    tokens = res.json()
    assert "access_token" in tokens
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_register_and_rbac(client: TestClient) -> None:
    email = "viewer@example.com"
    reg = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Viewer One"},
    )
    assert reg.status_code == 201
    login = client.post(
        "/v1/auth/login",
        data={"username": email, "password": "password123"},
    )
    token = login.json()["access_token"]
    forbidden = client.get("/v1/audit", headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == 403
