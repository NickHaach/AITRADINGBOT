"""Sync Redis JSON key-value helpers with fail-open semantics."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ai_trading_shared.utils.logging import get_logger

logger = get_logger(__name__)

CALIBRATION_KEY = "learning:calibration:last_fit"


class RedisJsonStore:
    """Tiny sync Redis wrapper. Connection failures return None / False."""

    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._client = None

    def _connect(self):
        if self._client is not None:
            return self._client
        try:
            import redis

            self._client = redis.from_url(self._url, decode_responses=True, socket_connect_timeout=0.5)
            # ping lazily on first use
            self._client.ping()
            return self._client
        except Exception:
            logger.debug("redis_kv_unavailable", url=self._url)
            self._client = None
            return None

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        client = self._connect()
        if client is None:
            return None
        try:
            raw = client.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            logger.debug("redis_kv_get_failed", key=key)
            return None

    def set_json(self, key: str, value: Dict[str, Any], *, ttl_seconds: Optional[int] = None) -> bool:
        client = self._connect()
        if client is None:
            return False
        try:
            payload = json.dumps(value)
            if ttl_seconds:
                client.setex(key, ttl_seconds, payload)
            else:
                client.set(key, payload)
            return True
        except Exception:
            logger.debug("redis_kv_set_failed", key=key)
            return False
