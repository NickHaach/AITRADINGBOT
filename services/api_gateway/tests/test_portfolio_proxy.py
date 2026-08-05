"""Auth-gated portfolio proxy tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api_gateway.main import app


def _admin_token(client: TestClient) -> str:
    res = client.post(
        "/v1/auth/login",
        data={"username": "admin@local.dev", "password": "ChangeMeAdmin123!"},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def _viewer_token(client: TestClient) -> str:
    email = "proxy-viewer@example.com"
    client.post(
        "/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": "Viewer"},
    )
    res = client.post(
        "/v1/auth/login",
        data={"username": email, "password": "password123"},
    )
    return res.json()["access_token"]


def test_portfolio_requires_auth() -> None:
    client = TestClient(app)
    assert client.get("/v1/portfolio").status_code == 401


def test_portfolio_proxy_ok_for_viewer() -> None:
    client = TestClient(app)
    token = _viewer_token(client)
    fake = {"cash": 100000, "equity": 100000, "positions": [], "drawdown": 0.0}

    with patch("api_gateway.main._proxy_portfolio", new_callable=AsyncMock) as mock_proxy:
        mock_proxy.return_value = fake
        res = client.get("/v1/portfolio", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["equity"] == 100000
    mock_proxy.assert_awaited()


def test_portfolio_run_forbidden_for_viewer() -> None:
    client = TestClient(app)
    token = _viewer_token(client)
    res = client.post("/v1/portfolio/run", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_portfolio_run_allowed_for_admin() -> None:
    client = TestClient(app)
    token = _admin_token(client)
    with patch("api_gateway.main._proxy_portfolio", new_callable=AsyncMock) as mock_proxy:
        mock_proxy.return_value = {"approved_trades": 0}
        res = client.post("/v1/portfolio/run", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
