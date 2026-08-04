"""Alpaca broker adapter — paper or live, gated by dual enablement flags."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import uuid4

import httpx

from ai_trading_shared.domain.entities import Order, Trade
from ai_trading_shared.domain.enums import OrderStatus, OrderType, Side, new_id
from ai_trading_shared.utils.logging import get_logger

logger = get_logger(__name__)


class AlpacaBroker:
    """Thin REST adapter for Alpaca trading API.

    Live submissions require ``live_enabled=True``. Paper base URL is the default.
    """

    name = "alpaca"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str = "https://paper-api.alpaca.markets",
        *,
        live_enabled: bool = False,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._base_url = base_url.rstrip("/")
        self._live_enabled = live_enabled
        self._orders: Dict[str, Order] = {}
        self._trades: list[Trade] = []
        if "paper-api" not in self._base_url and not live_enabled:
            raise RuntimeError(
                "Alpaca live base URL requires live_enabled=True "
                "(set ENABLE_LIVE_TRADING=true and EXECUTION_MODE=live)"
            )

    def _headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self._api_key,
            "APCA-API-SECRET-KEY": self._secret_key,
            "Content-Type": "application/json",
        }

    async def submit(self, order: Order, fill_price: Decimal) -> Order:
        if "paper-api" not in self._base_url and not self._live_enabled:
            raise RuntimeError("Live Alpaca trading is disabled")

        payload = {
            "symbol": order.ticker,
            "qty": str(order.quantity),
            "side": order.side.value,
            "type": _map_order_type(order.order_type),
            "time_in_force": "day",
        }
        if order.limit_price is not None:
            payload["limit_price"] = str(order.limit_price)
        if order.stop_price is not None:
            payload["stop_price"] = str(order.stop_price)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/v2/orders",
                headers=self._headers(),
                json=payload,
            )
            if response.status_code >= 400:
                logger.error("alpaca_order_rejected", body=response.text)
                return order.model_copy(
                    update={
                        "status": OrderStatus.REJECTED,
                        "reject_reason": response.text[:500],
                        "broker": self.name,
                        "updated_at": datetime.utcnow(),
                    }
                )
            data = response.json()

        broker_id = str(data.get("id") or uuid4())
        status = _map_alpaca_status(str(data.get("status", "accepted")))
        filled_qty = Decimal(str(data.get("filled_qty") or 0))
        avg_price = (
            Decimal(str(data["filled_avg_price"]))
            if data.get("filled_avg_price")
            else (fill_price if status == OrderStatus.FILLED else None)
        )
        updated = order.model_copy(
            update={
                "status": status,
                "broker": self.name,
                "broker_order_id": broker_id,
                "filled_quantity": filled_qty,
                "average_fill_price": avg_price,
                "updated_at": datetime.utcnow(),
            }
        )
        self._orders[broker_id] = updated
        if status == OrderStatus.FILLED and avg_price is not None:
            self._trades.append(
                Trade(
                    id=new_id(),
                    order_id=updated.id,
                    ticker=updated.ticker,
                    side=updated.side,
                    quantity=updated.filled_quantity or updated.quantity,
                    price=avg_price,
                )
            )
        return updated

    async def cancel(self, broker_order_id: str) -> bool:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.delete(
                f"{self._base_url}/v2/orders/{broker_order_id}",
                headers=self._headers(),
            )
        ok = response.status_code < 300
        if ok and broker_order_id in self._orders:
            self._orders[broker_order_id] = self._orders[broker_order_id].model_copy(
                update={"status": OrderStatus.CANCELLED, "updated_at": datetime.utcnow()}
            )
        return ok

    async def get_order(self, broker_order_id: str) -> Optional[Order]:
        if broker_order_id in self._orders:
            return self._orders[broker_order_id]
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self._base_url}/v2/orders/{broker_order_id}",
                headers=self._headers(),
            )
            if response.status_code >= 400:
                return None
            data = response.json()
        return Order(
            ticker=str(data.get("symbol", "")),
            side=Side(str(data.get("side", "buy"))),
            order_type=_unmap_order_type(str(data.get("type", "market"))),
            quantity=Decimal(str(data.get("qty") or 0)),
            status=_map_alpaca_status(str(data.get("status", "new"))),
            broker=self.name,
            broker_order_id=str(data.get("id")),
            filled_quantity=Decimal(str(data.get("filled_qty") or 0)),
            average_fill_price=(
                Decimal(str(data["filled_avg_price"]))
                if data.get("filled_avg_price")
                else None
            ),
        )

    @property
    def trades(self) -> list[Trade]:
        return list(self._trades)


def build_broker_from_settings(settings: Any) -> Any:
    """Factory: paper by default; Alpaca only when keys present."""
    from execution.service import PaperBroker

    settings.assert_live_trading_allowed()
    if settings.execution_mode == "paper" or not settings.broker_alpaca_api_key:
        return PaperBroker()
    key = settings.broker_alpaca_api_key.get_secret_value()
    secret = (
        settings.broker_alpaca_secret_key.get_secret_value()
        if settings.broker_alpaca_secret_key
        else ""
    )
    if not key or not secret:
        return PaperBroker()
    return AlpacaBroker(
        api_key=key,
        secret_key=secret,
        base_url=settings.broker_alpaca_base_url,
        live_enabled=settings.enable_live_trading and settings.execution_mode == "live",
    )


def _map_order_type(order_type: OrderType) -> str:
    return {
        OrderType.MARKET: "market",
        OrderType.LIMIT: "limit",
        OrderType.STOP: "stop",
        OrderType.STOP_LIMIT: "stop_limit",
    }[order_type]


def _unmap_order_type(value: str) -> OrderType:
    return {
        "market": OrderType.MARKET,
        "limit": OrderType.LIMIT,
        "stop": OrderType.STOP,
        "stop_limit": OrderType.STOP_LIMIT,
    }.get(value, OrderType.MARKET)


def _map_alpaca_status(value: str) -> OrderStatus:
    mapping = {
        "new": OrderStatus.SUBMITTED,
        "accepted": OrderStatus.SUBMITTED,
        "pending_new": OrderStatus.PENDING,
        "partially_filled": OrderStatus.PARTIAL,
        "filled": OrderStatus.FILLED,
        "canceled": OrderStatus.CANCELLED,
        "cancelled": OrderStatus.CANCELLED,
        "expired": OrderStatus.EXPIRED,
        "rejected": OrderStatus.REJECTED,
    }
    return mapping.get(value.lower(), OrderStatus.SUBMITTED)
