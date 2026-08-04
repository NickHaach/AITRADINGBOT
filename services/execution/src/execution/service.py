"""Execution Engine — pluggable broker integrations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import uuid4

from ai_trading_shared.domain.entities import Order, Trade
from ai_trading_shared.domain.enums import OrderStatus, new_id


class BrokerPort(Protocol):
    name: str

    async def submit(self, order: Order, fill_price: Decimal) -> Order: ...

    async def cancel(self, broker_order_id: str) -> bool: ...

    async def get_order(self, broker_order_id: str) -> Order | None: ...


class PaperBroker:
    """Simulated broker that fills market orders immediately."""

    name = "paper"

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        self._trades: list[Trade] = []

    async def submit(self, order: Order, fill_price: Decimal) -> Order:
        broker_id = f"paper-{uuid4()}"
        filled = order.model_copy(
            update={
                "status": OrderStatus.FILLED,
                "broker": self.name,
                "broker_order_id": broker_id,
                "filled_quantity": order.quantity,
                "average_fill_price": fill_price,
                "updated_at": datetime.utcnow(),
            }
        )
        self._orders[broker_id] = filled
        self._trades.append(
            Trade(
                id=new_id(),
                order_id=filled.id,
                ticker=filled.ticker,
                side=filled.side,
                quantity=filled.quantity,
                price=fill_price,
                fees=Decimal("0"),
            )
        )
        return filled

    async def cancel(self, broker_order_id: str) -> bool:
        order = self._orders.get(broker_order_id)
        if order is None or order.status == OrderStatus.FILLED:
            return False
        self._orders[broker_order_id] = order.model_copy(
            update={"status": OrderStatus.CANCELLED, "updated_at": datetime.utcnow()}
        )
        return True

    async def get_order(self, broker_order_id: str) -> Order | None:
        return self._orders.get(broker_order_id)

    @property
    def trades(self) -> list[Trade]:
        return list(self._trades)


class ExecutionService:
    """Submits risk-approved orders through the configured broker."""

    def __init__(self, broker: BrokerPort, *, live_enabled: bool = False) -> None:
        self._broker = broker
        self._live_enabled = live_enabled

    async def execute(self, order: Order, fill_price: Decimal) -> Order:
        if self._broker.name != "paper" and not self._live_enabled:
            raise RuntimeError("Live broker execution is disabled")
        return await self._broker.submit(order, fill_price)
