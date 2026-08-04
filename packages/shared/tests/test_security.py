"""Shared package unit tests — security & settings."""

from ai_trading_shared.config import Settings
from ai_trading_shared.domain.enums import Role
from ai_trading_shared.security import (
    create_access_token,
    decode_token,
    hash_password,
    role_at_least,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("secure-pass-123")
    assert verify_password("secure-pass-123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip() -> None:
    token = create_access_token(
        subject="11111111-1111-1111-1111-111111111111",
        role=Role.TRADER,
        secret_key="test-secret",
        expires_minutes=5,
    )
    payload = decode_token(token, "test-secret")
    assert payload["role"] == "trader"
    assert payload["type"] == "access"


def test_rbac_hierarchy() -> None:
    assert role_at_least(Role.ADMIN, Role.TRADER)
    assert role_at_least(Role.TRADER, Role.ANALYST)
    assert not role_at_least(Role.VIEWER, Role.TRADER)


def test_live_trading_guard() -> None:
    settings = Settings(execution_mode="paper", enable_live_trading=False)
    try:
        Settings(execution_mode="live", enable_live_trading=False).assert_live_trading_allowed()
        raised = False
    except RuntimeError:
        raised = True
    assert raised
    settings.assert_live_trading_allowed()  # paper is fine
