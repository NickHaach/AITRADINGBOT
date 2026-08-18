"""Alpaca broker unit tests (no network)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_trading_shared.config import Settings
from ai_trading_shared.domain.entities import Order
from ai_trading_shared.domain.enums import OrderStatus, OrderType, Side
from execution.brokers.alpaca import AlpacaBroker, build_broker_from_settings
from execution.service import PaperBroker


def test_live_url_requires_flag() -> None:
    with pytest.raises(RuntimeError, match="live_enabled"):
        AlpacaBroker(
            api_key="k",
            secret_key="s",
            base_url="https://api.alpaca.markets",
            live_enabled=False,
        )


def test_factory_defaults_to_paper() -> None:
    settings = Settings(execution_mode="paper", enable_live_trading=False)
    broker = build_broker_from_settings(settings)
    assert isinstance(broker, PaperBroker)


def test_factory_uses_alpaca_paper_with_keys() -> None:
    from pydantic import SecretStr

    settings = Settings(
        execution_mode="paper",
        enable_live_trading=False,
        broker_alpaca_api_key=SecretStr("key"),
        broker_alpaca_secret_key=SecretStr("secret"),
        broker_alpaca_base_url="https://paper-api.alpaca.markets",
    )
    broker = build_broker_from_settings(settings)
    assert isinstance(broker, AlpacaBroker)
    assert not broker.is_live_endpoint


def test_factory_falls_back_live_url_without_flags() -> None:
    from pydantic import SecretStr

    settings = Settings(
        execution_mode="paper",
        enable_live_trading=False,
        broker_alpaca_api_key=SecretStr("key"),
        broker_alpaca_secret_key=SecretStr("secret"),
        broker_alpaca_base_url="https://api.alpaca.markets",
    )
    broker = build_broker_from_settings(settings)
    assert isinstance(broker, AlpacaBroker)
    assert not broker.is_live_endpoint


@pytest.mark.asyncio
async def test_alpaca_submit_maps_fill() -> None:
    broker = AlpacaBroker(
        api_key="k",
        secret_key="s",
        base_url="https://paper-api.alpaca.markets",
        live_enabled=False,
    )
    order = Order(
        ticker="AAPL",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "alpaca-1",
        "status": "filled",
        "filled_qty": "1",
        "filled_avg_price": "190.5",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("execution.brokers.alpaca.httpx.AsyncClient", return_value=mock_client):
        filled = await broker.submit(order, Decimal("190"))

    assert filled.status == OrderStatus.FILLED
    assert filled.broker_order_id == "alpaca-1"
    assert filled.average_fill_price == Decimal("190.5")
