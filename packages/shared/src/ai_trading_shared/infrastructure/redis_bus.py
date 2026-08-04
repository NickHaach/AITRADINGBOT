"""Redis Streams event bus implementation."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from ai_trading_shared.events import DomainEvent
from ai_trading_shared.utils.logging import get_logger

logger = get_logger(__name__)


class RedisEventBus:
    """Publish/consume domain events via Redis Streams + consumer groups."""

    def __init__(self, redis_url: str) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)

    async def close(self) -> None:
        await self._redis.aclose()

    async def ensure_group(self, stream: str, group: str) -> None:
        try:
            await self._redis.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, stream: str, event: DomainEvent) -> str:
        payload = event.model_dump(mode="json")
        message_id = await self._redis.xadd(
            stream,
            {"data": json.dumps(payload)},
        )
        logger.debug("event_published", stream=stream, event_type=event.event_type, id=message_id)
        return message_id

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 2000,
    ) -> list[tuple[str, DomainEvent]]:
        await self.ensure_group(stream, group)
        results = await self._redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
            block=block_ms,
        )
        events: list[tuple[str, DomainEvent]] = []
        if not results:
            return events
        for _stream_name, messages in results:
            for message_id, fields in messages:
                data = json.loads(fields["data"])
                events.append((message_id, DomainEvent.model_validate(data)))
        return events

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        await self._redis.xack(stream, group, message_id)

    async def ping(self) -> bool:
        return bool(await self._redis.ping())

    @property
    def client(self) -> Any:
        return self._redis
