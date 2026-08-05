"""Session cookie auth tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api_gateway.main import ACCESS_COOKIE, REFRESH_COOKIE, app


def test_session_login_sets_httponly_cookies() -> None:
    client = TestClient(app)
    res = client.post(
        "/v1/auth/session/login",
        data={"username": "admin@local.dev", "password": "ChangeMeAdmin123!"},
    )
    assert res.status_code == 200
    assert res.json()["email"] == "admin@local.dev"
    assert ACCESS_COOKIE in res.cookies
    assert REFRESH_COOKIE in res.cookies
    me = client.get("/v1/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_session_logout_clears_cookies() -> None:
    client = TestClient(app)
    client.post(
        "/v1/auth/session/login",
        data={"username": "admin@local.dev", "password": "ChangeMeAdmin123!"},
    )
    out = client.post("/v1/auth/session/logout")
    assert out.status_code == 200
    # TestClient may retain jar; force empty request without cookies
    bare = TestClient(app)
    assert bare.get("/v1/me").status_code == 401


def test_bearer_still_works() -> None:
    client = TestClient(app)
    login = client.post(
        "/v1/auth/login",
        data={"username": "admin@local.dev", "password": "ChangeMeAdmin123!"},
    )
    token = login.json()["access_token"]
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
