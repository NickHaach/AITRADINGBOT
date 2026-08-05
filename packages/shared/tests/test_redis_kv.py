"""Redis KV store tests (no live Redis required)."""

from __future__ import annotations

from ai_trading_shared.infrastructure.redis_kv import RedisJsonStore


def test_redis_kv_fail_open_without_server() -> None:
    store = RedisJsonStore("redis://127.0.0.1:1/0")  # closed port
    assert store.get_json("missing") is None
    assert store.set_json("k", {"a": 1}) is False
