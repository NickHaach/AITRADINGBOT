"""Deterministic synthetic OHLCV generator for offline development."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List

import numpy as np

from ai_trading_shared.domain.enums import AssetClass
from market_data.domain.models import OHLCVBar, Quote


# Seed prices / drift / vol for equities, forex, and crypto
_SPECS: Dict[str, Dict[str, float]] = {
    # Equities
    "AAPL": {"px": 190.0, "mu": 0.0004, "sigma": 0.012},
    "MSFT": {"px": 420.0, "mu": 0.0003, "sigma": 0.011},
    "NVDA": {"px": 120.0, "mu": 0.0010, "sigma": 0.025},
    "SPY": {"px": 520.0, "mu": 0.0002, "sigma": 0.008},
    "QQQ": {"px": 450.0, "mu": 0.0003, "sigma": 0.010},
    "XOM": {"px": 110.0, "mu": 0.0001, "sigma": 0.014},
    "JPM": {"px": 195.0, "mu": 0.0002, "sigma": 0.013},
    "TSLA": {"px": 250.0, "mu": 0.0005, "sigma": 0.030},
    # Forex (spot FX, 24h-ish)
    "EURUSD": {"px": 1.0850, "mu": 0.00002, "sigma": 0.0045},
    "GBPUSD": {"px": 1.2720, "mu": 0.00001, "sigma": 0.0050},
    "USDJPY": {"px": 156.40, "mu": 0.00003, "sigma": 0.0055},
    "AUDUSD": {"px": 0.6620, "mu": 0.00001, "sigma": 0.0058},
    "USDCAD": {"px": 1.3640, "mu": 0.00001, "sigma": 0.0048},
    # Crypto
    "BTCUSD": {"px": 65000.0, "mu": 0.0008, "sigma": 0.035},
    "ETHUSD": {"px": 3450.0, "mu": 0.0009, "sigma": 0.040},
    "SOLUSD": {"px": 145.0, "mu": 0.0012, "sigma": 0.050},
    "BTC-USD": {"px": 65000.0, "mu": 0.0008, "sigma": 0.035},  # alias
}

_FOREX = {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EUR/USD", "GBP/USD"}
_CRYPTO = {"BTCUSD", "ETHUSD", "SOLUSD", "BTC-USD", "ETH-USD"}

EQUITY_TICKERS = ["AAPL", "MSFT", "NVDA", "SPY", "QQQ", "XOM", "JPM"]
FOREX_TICKERS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
CRYPTO_TICKERS = ["BTCUSD", "ETHUSD", "SOLUSD"]
DEFAULT_UNIVERSE = EQUITY_TICKERS + FOREX_TICKERS + CRYPTO_TICKERS


def normalize_ticker(ticker: str) -> str:
    t = ticker.upper().replace("/", "").replace("_", "")
    if t == "BTC-USD":
        return "BTCUSD"
    if t == "ETH-USD":
        return "ETHUSD"
    return t


def asset_class_for(ticker: str) -> AssetClass:
    t = normalize_ticker(ticker)
    if t in _FOREX or t in {x.replace("/", "") for x in _FOREX}:
        return AssetClass.FOREX
    if t in _CRYPTO or t.startswith("BTC") or t.startswith("ETH") or t.startswith("SOL"):
        return AssetClass.CRYPTO
    if t in {"SPY", "QQQ"}:
        return AssetClass.ETF
    return AssetClass.STOCK


def _decimals(asset_class: AssetClass) -> int:
    if asset_class == AssetClass.FOREX:
        return 5
    if asset_class == AssetClass.CRYPTO:
        return 2
    return 4


class MockMarketDataProvider:
    """GBM-style bar generator with stable seeds per ticker + live quote jitter."""

    name = "mock"

    async def fetch_ohlcv(
        self,
        ticker: str,
        *,
        lookback_days: int = 60,
        asset_class: AssetClass = AssetClass.STOCK,
    ) -> List[OHLCVBar]:
        symbol = normalize_ticker(ticker)
        klass = asset_class_for(symbol) if asset_class == AssetClass.STOCK else asset_class
        # Prefer explicit class from caller when not default stock for known FX/crypto
        if symbol in _FOREX or symbol in {normalize_ticker(x) for x in _FOREX}:
            klass = AssetClass.FOREX
        elif symbol in _CRYPTO:
            klass = AssetClass.CRYPTO

        spec = _SPECS.get(symbol) or _SPECS.get(ticker.upper()) or {
            "px": 100.0,
            "mu": 0.0002,
            "sigma": 0.015,
        }
        seed = abs(hash(symbol)) % (2**32)
        rng = np.random.default_rng(seed)
        n = max(lookback_days, 5)
        now = datetime.now(timezone.utc).replace(hour=21, minute=0, second=0, microsecond=0)
        places = _decimals(klass)

        price = spec["px"]
        bars: List[OHLCVBar] = []
        for i in range(n, 0, -1):
            shock = rng.normal(spec["mu"], spec["sigma"])
            open_px = price
            close_px = max(1e-6, open_px * float(np.exp(shock)))
            high_px = max(open_px, close_px) * float(1.0 + abs(rng.normal(0, 0.002)))
            low_px = min(open_px, close_px) * float(1.0 - abs(rng.normal(0, 0.002)))
            vol_base = 1.0e8 if klass == AssetClass.FOREX else (5.0e3 if klass == AssetClass.CRYPTO else 1.0e6)
            volume = Decimal(str(round(float(rng.uniform(vol_base, vol_base * 6)), 2)))
            ts = now - timedelta(days=i)
            bars.append(
                OHLCVBar(
                    ticker=symbol,
                    asset_class=klass,
                    timestamp=ts,
                    open=Decimal(str(round(open_px, places))),
                    high=Decimal(str(round(high_px, places))),
                    low=Decimal(str(round(low_px, places))),
                    close=Decimal(str(round(close_px, places))),
                    volume=volume,
                    vwap=Decimal(str(round((open_px + close_px) / 2.0, places))),
                )
            )
            price = close_px
        return bars

    async def fetch_quote(self, ticker: str) -> Quote:
        symbol = normalize_ticker(ticker)
        bars = await self.fetch_ohlcv(symbol, lookback_days=5)
        last = bars[-1].close
        places = _decimals(asset_class_for(symbol))
        # Time-bucketed jitter so the WS tape moves every second
        bucket = int(time.time())
        rng = np.random.default_rng(abs(hash((symbol, bucket))) % (2**32))
        sigma = 0.00035 if asset_class_for(symbol) == AssetClass.FOREX else 0.0009
        jitter = Decimal(str(float(np.exp(rng.normal(0, sigma)))))
        last = Decimal(str(round(float(last * jitter), places)))
        spread_bps = Decimal("0.0002") if asset_class_for(symbol) == AssetClass.FOREX else Decimal("0.0005")
        spread = last * spread_bps
        return Quote(
            ticker=symbol,
            bid=last - spread / 2,
            ask=last + spread / 2,
            bid_size=Decimal("100000") if asset_class_for(symbol) == AssetClass.FOREX else Decimal("100"),
            ask_size=Decimal("100000") if asset_class_for(symbol) == AssetClass.FOREX else Decimal("100"),
            last=last,
            timestamp=datetime.now(timezone.utc),
        )
