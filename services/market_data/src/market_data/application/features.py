"""Volatility and return feature engineering."""

from __future__ import annotations

from datetime import datetime
from typing import List, Sequence

import numpy as np

from market_data.domain.models import MarketFeatures, OHLCVBar


def compute_features(bars: Sequence[OHLCVBar]) -> MarketFeatures:
    """Compute returns, realized vol, volume z-score, and trend metrics.

    Requires at least 5 bars; prefers 20+ for stable vol estimates.
    """
    if len(bars) < 5:
        raise ValueError("Need at least 5 OHLCV bars to compute features")

    ordered = sorted(bars, key=lambda b: b.timestamp)
    closes = np.array([float(b.close) for b in ordered], dtype=np.float64)
    volumes = np.array([float(b.volume) for b in ordered], dtype=np.float64)

    log_returns = np.diff(np.log(np.clip(closes, 1e-12, None)))
    returns_1d = float((closes[-1] / closes[-2]) - 1.0) if len(closes) >= 2 else 0.0
    returns_5d = float((closes[-1] / closes[-6]) - 1.0) if len(closes) >= 6 else returns_1d
    returns_20d = float((closes[-1] / closes[-21]) - 1.0) if len(closes) >= 21 else returns_5d

    vol_10 = _realized_vol(log_returns, 10)
    vol_20 = _realized_vol(log_returns, 20)

    vol_window = volumes[-20:] if len(volumes) >= 20 else volumes
    vol_mean = float(np.mean(vol_window))
    vol_std = float(np.std(vol_window)) or 1.0
    volume_z = float((volumes[-1] - vol_mean) / vol_std)

    window = closes[-20:] if len(closes) >= 20 else closes
    high_20 = float(np.max(window))
    low_20 = float(np.min(window))
    last = float(closes[-1])
    distance_from_high = float((last / high_20) - 1.0) if high_20 else 0.0

    # simple trend: slope of normalized closes over available window
    x = np.arange(len(window), dtype=np.float64)
    slope = float(np.polyfit(x, window / window[0], 1)[0]) if len(window) >= 3 else 0.0
    trend_strength = float(np.clip(slope * 10.0, -1.0, 1.0))

    # liquidity: higher volume + tighter relative range → higher score
    avg_range = float(np.mean([(float(b.high) - float(b.low)) / max(float(b.close), 1e-9) for b in ordered[-10:]]))
    liquidity = float(np.clip(0.5 + 0.1 * volume_z - 2.0 * avg_range, 0.0, 1.0))

    return MarketFeatures(
        ticker=ordered[-1].ticker,
        as_of=ordered[-1].timestamp if isinstance(ordered[-1].timestamp, datetime) else datetime.utcnow(),
        last_price=last,
        returns_1d=returns_1d,
        returns_5d=returns_5d,
        returns_20d=returns_20d,
        volatility_10d=vol_10,
        volatility_20d=vol_20,
        volume_zscore_20d=volume_z,
        liquidity_score=liquidity,
        trend_strength=trend_strength,
        high_20d=high_20,
        low_20d=low_20,
        distance_from_high_20d=distance_from_high,
        bars_used=len(ordered),
    )


def _realized_vol(log_returns: np.ndarray, window: int) -> float:
    if len(log_returns) == 0:
        return 0.0
    sample = log_returns[-window:] if len(log_returns) >= window else log_returns
    return float(np.std(sample) * np.sqrt(252.0))


def annualized_vol_from_closes(closes: List[float], window: int = 20) -> float:
    arr = np.array(closes, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    rets = np.diff(np.log(np.clip(arr, 1e-12, None)))
    return _realized_vol(rets, window)
