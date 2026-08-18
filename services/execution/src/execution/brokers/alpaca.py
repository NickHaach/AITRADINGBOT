"""Alpaca broker adapter — paper or live, gated by dual enablement flags."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import uuid4

import httpx

from ai_trading_shared.domain.entities import Order, Trade
from ai_trading_shared.domain.enums import OrderStatus, OrderType, Side, new_id
from ai_trading_shared.utils.logging import get_logger

logger = get_logger(__name__)

PAPER_BASE = "https://paper-api.alpaca.markets"
LIVE_BASE = "https://api.alpaca.markets"


class AlpacaBroker:
    """Thin REST adapter for Alpaca trading API.

    Paper base URL works with API keys alone.
    Live base URL requires ``live_enabled=True`` (dual env flags).
    """

    name = "alpaca"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str = PAPER_BASE,
        *,
        live_enabled: bool = False,
        poll_attempts: int = 8,
        poll_interval_sec: float = 0.35,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._base_url = base_url.rstrip("/")
        self._live_enabled = live_enabled
        self._poll_attempts = max(1, poll_attempts)
        self._poll_interval_sec = max(0.05, poll_interval_sec)
        self._orders: Dict[str, Order] = {}
        self._trades: list[Trade] = []
        if self.is_live_endpoint and not live_enabled:
            raise RuntimeError(
                "Alpaca live base URL requires live_enabled=True "
                "(set ENABLE_LIVE_TRADING=true and EXECUTION_MODE=live)"
            )

    @property
    def is_live_endpoint(self) -> bool:
        return "paper-api" not in self._base_url

    def _headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self._api_key,
            "APCA-API-SECRET-KEY": self._secret_key,
            "Content-Type": "application/json",
        }

    async def ping_account(self) -> Dict[str, Any]:
        """Fetch account summary — used for connection health."""
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self._base_url}/v2/account",
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
        return {
            "id": data.get("id"),
            "status": data.get("status"),
            "currency": data.get("currency"),
            "cash": data.get("cash"),
            "equity": data.get("equity"),
            "buying_power": data.get("buying_power"),
            "pattern_day_trader": data.get("pattern_day_trader"),
            "trading_blocked": data.get("trading_blocked"),
            "paper": not self.is_live_endpoint,
        }

    async def submit(self, order: Order, fill_price: Decimal) -> Order:
        if self.is_live_endpoint and not self._live_enabled:
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
        if order.stop_price is not None and order.order_type in (
            OrderType.STOP,
            OrderType.STOP_LIMIT,
        ):
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
            # Market orders may accept first; poll briefly for fill.
            for _ in range(self._poll_attempts - 1):
                status = _map_alpaca_status(str(data.get("status", "accepted")))
                if status in (
                    OrderStatus.FILLED,
                    OrderStatus.REJECTED,
                    OrderStatus.CANCELLED,
                    OrderStatus.EXPIRED,
                ):
                    break
                await asyncio.sleep(self._poll_interval_sec)
                poll = await client.get(
                    f"{self._base_url}/v2/orders/{broker_id}",
                    headers=self._headers(),
                )
                if poll.status_code < 400:
                    data = poll.json()

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
                "filled_quantity": filled_qty if filled_qty > 0 else (
                    order.quantity if status == OrderStatus.FILLED else Decimal("0")
                ),
                "average_fill_price": avg_price,
                "updated_at": datetime.utcnow(),
            }
        )
        self._orders[broker_id] = updated
        if status == OrderStatus.FILLED and avg_price is not None:
            qty = updated.filled_quantity or updated.quantity
            self._trades.append(
                Trade(
                    id=new_id(),
                    order_id=updated.id,
                    ticker=updated.ticker,
                    side=updated.side,
                    quantity=qty,
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
    """Factory: local PaperBroker, or Alpaca when keys are set.

    - Keys + paper-api URL → Alpaca paper (practice money)
    - Keys + live URL + dual flags → Alpaca live (real money)
    - No keys → in-process PaperBroker
    """
    from execution.service import PaperBroker

    settings.assert_live_trading_allowed()
    key = (
        settings.broker_alpaca_api_key.get_secret_value()
        if settings.broker_alpaca_api_key
        else ""
    )
    secret = (
        settings.broker_alpaca_secret_key.get_secret_value()
        if settings.broker_alpaca_secret_key
        else ""
    )
    if not key or not secret:
        return PaperBroker()

    base = (settings.broker_alpaca_base_url or PAPER_BASE).rstrip("/")
    live_flags = bool(settings.enable_live_trading and settings.execution_mode == "live")
    wants_live = "paper-api" not in base

    if wants_live and not live_flags:
        logger.warning(
            "alpaca_live_url_without_flags_falling_back_to_paper_api",
            base_url=base,
        )
        base = PAPER_BASE

    return AlpacaBroker(
        api_key=key,
        secret_key=secret,
        base_url=base,
        live_enabled=live_flags and "paper-api" not in base,
    )


def broker_status_payload(broker: Any, settings: Any) -> Dict[str, Any]:
    """Serializable broker connection status for the desk UI."""
    name = getattr(broker, "name", "unknown")
    has_keys = bool(
        settings.broker_alpaca_api_key
        and settings.broker_alpaca_secret_key
        and settings.broker_alpaca_api_key.get_secret_value()
        and settings.broker_alpaca_secret_key.get_secret_value()
    )
    base = settings.broker_alpaca_base_url or PAPER_BASE
    live_flags = bool(settings.enable_live_trading and settings.execution_mode == "live")
    is_alpaca_paper = name == "alpaca" and "paper-api" in getattr(broker, "_base_url", base)
    is_alpaca_live = name == "alpaca" and getattr(broker, "is_live_endpoint", False)
    return {
        "broker": name,
        "connected": name == "alpaca",
        "mode": "live" if is_alpaca_live else ("alpaca_paper" if is_alpaca_paper else "local_paper"),
        "has_alpaca_keys": has_keys,
        "base_url": getattr(broker, "_base_url", None) if name == "alpaca" else None,
        "execution_mode": settings.execution_mode,
        "enable_live_trading": settings.enable_live_trading,
        "live_trading_armed": live_flags and is_alpaca_live,
        "live_connect_allowed": live_flags,
        "setup_url": (
            "https://app.alpaca.markets/dashboard/overview"
            if is_alpaca_live
            else "https://app.alpaca.markets/paper/dashboard/overview"
        ),
        "docs": [
            "Create a free Alpaca account (paper trading is default).",
            "Generate Paper API Key + Secret under Alpaca → Paper Trading → API Keys.",
            "Connect paper from the desk Broker tab, or put keys in .env.",
            "Real money: set EXECUTION_MODE=live AND ENABLE_LIVE_TRADING=true, restart, "
            "then use Connect live with live API keys and type LIVE to confirm.",
        ],
    }


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
