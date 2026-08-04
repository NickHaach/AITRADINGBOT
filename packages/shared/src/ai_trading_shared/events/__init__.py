from __future__ import annotations
"""Domain event bus contracts and event payloads."""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import Field

from ai_trading_shared.domain.enums import DomainModel, new_id


class DomainEvent(DomainModel):
    """Base envelope for all platform events."""

    event_id: UUID = Field(default_factory=new_id)
    event_type: str
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NewsIngested(DomainEvent):
    event_type: str = "news.ingested"


class NewsClassified(DomainEvent):
    event_type: str = "news.classified"


class AnnouncementParsed(DomainEvent):
    event_type: str = "announcement.parsed"


class SignalGenerated(DomainEvent):
    event_type: str = "signal.generated"


class RiskChecked(DomainEvent):
    event_type: str = "risk.checked"


class OrderSubmitted(DomainEvent):
    event_type: str = "order.submitted"


class OrderFilled(DomainEvent):
    event_type: str = "order.filled"


class TradeClosed(DomainEvent):
    event_type: str = "trade.closed"


class EventPublisher(Protocol):
    async def publish(self, stream: str, event: DomainEvent) -> str:
        """Publish event to a named stream; return message id."""
        ...


class EventConsumer(Protocol):
    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 2000,
    ) -> list[tuple[str, DomainEvent]]:
        """Consume events from a consumer group."""
        ...


# Canonical stream names
STREAM_NEWS = "events:news"
STREAM_ANNOUNCEMENTS = "events:announcements"
STREAM_SIGNALS = "events:signals"
STREAM_ORDERS = "events:orders"
STREAM_TRADES = "events:trades"
STREAM_MACRO = "events:macro"
STREAM_GEO = "events:geopolitical"
STREAM_SENTIMENT = "events:sentiment"
STREAM_MARKET = "events:market"
