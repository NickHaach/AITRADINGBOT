"""Backtesting engine — replay OHLCV (+ optional news) for strategy evaluation."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Sequence

import numpy as np

from backtesting.domain.models import BacktestBar, BacktestResult, BacktestTrade, NewsEvent


class MomentumNewsStrategy:
    """Long when 5d momentum > 0 and optional news sentiment not deeply negative."""

    name = "momentum_news_v1"

    def __init__(self, lookback: int = 5, sentiment_floor: float = -0.4) -> None:
        self.lookback = lookback
        self.sentiment_floor = sentiment_floor

    def signal(
        self,
        closes: Sequence[float],
        sentiment: Optional[float] = None,
    ) -> int:
        """Return 1 long, 0 flat, -1 short (short unused in long-only mode)."""
        if len(closes) <= self.lookback:
            return 0
        mom = closes[-1] / closes[-1 - self.lookback] - 1.0
        if sentiment is not None and sentiment < self.sentiment_floor:
            return 0
        if mom > 0.01:
            return 1
        if mom < -0.01:
            return 0  # exit / stay flat (long-only)
        return 0


class BacktestEngine:
    """Event-driven long-only backtester with cash accounting."""

    def __init__(self, initial_cash: float = 100_000.0, position_pct: float = 0.95) -> None:
        self.initial_cash = initial_cash
        self.position_pct = position_pct
        self._results: List[BacktestResult] = []

    def run(
        self,
        *,
        ticker: str,
        bars: Sequence[BacktestBar],
        strategy: Optional[MomentumNewsStrategy] = None,
        news: Optional[Sequence[NewsEvent]] = None,
    ) -> BacktestResult:
        if len(bars) < 10:
            raise ValueError("Need at least 10 bars for backtest")
        strategy = strategy or MomentumNewsStrategy()
        news = list(news or [])
        news_by_day: Dict[str, float] = {}
        for event in news:
            if event.ticker.upper() != ticker.upper():
                continue
            key = event.timestamp.date().isoformat()
            news_by_day[key] = event.sentiment_score

        cash = self.initial_cash
        qty = 0.0
        equity_curve: List[float] = []
        trades: List[BacktestTrade] = []
        closes_window: List[float] = []

        ordered = sorted(bars, key=lambda b: b.timestamp)
        for bar in ordered:
            closes_window.append(bar.close)
            day_key = bar.timestamp.date().isoformat()
            sentiment = news_by_day.get(day_key)
            sig = strategy.signal(closes_window, sentiment)

            if sig == 1 and qty == 0 and cash > 0:
                notional = cash * self.position_pct
                qty = notional / bar.close
                cash -= qty * bar.close
                trades.append(
                    BacktestTrade(
                        timestamp=bar.timestamp,
                        side="buy",
                        price=bar.close,
                        quantity=qty,
                        reason="momentum_entry",
                    )
                )
            elif sig == 0 and qty > 0:
                cash += qty * bar.close
                trades.append(
                    BacktestTrade(
                        timestamp=bar.timestamp,
                        side="sell",
                        price=bar.close,
                        quantity=qty,
                        reason="momentum_exit",
                    )
                )
                qty = 0.0

            equity_curve.append(cash + qty * bar.close)

        # mark final position
        final_equity = equity_curve[-1]
        total_return = final_equity / self.initial_cash - 1.0
        max_dd = _max_drawdown(equity_curve)
        sharpe = _sharpe(equity_curve)
        win_rate = _win_rate(trades, ordered)

        result = BacktestResult(
            strategy_name=strategy.name,
            ticker=ticker.upper(),
            started_at=ordered[0].timestamp,
            ended_at=ordered[-1].timestamp,
            initial_cash=self.initial_cash,
            final_equity=round(final_equity, 2),
            total_return=round(total_return, 6),
            max_drawdown=round(max_dd, 6),
            sharpe=round(sharpe, 4),
            win_rate=round(win_rate, 4),
            trade_count=len(trades),
            equity_curve=[round(x, 2) for x in equity_curve[:: max(1, len(equity_curve) // 50)]],
            trades=trades,
            metrics={
                "bars": float(len(ordered)),
                "news_days": float(len(news_by_day)),
                "ending_position_qty": qty,
            },
        )
        self._results.append(result)
        return result

    def list_results(self) -> List[BacktestResult]:
        return list(self._results)


def _max_drawdown(equity: Sequence[float]) -> float:
    if not equity:
        return 0.0
    arr = np.array(equity, dtype=np.float64)
    peak = np.maximum.accumulate(arr)
    dd = (peak - arr) / np.clip(peak, 1e-12, None)
    return float(np.max(dd))


def _sharpe(equity: Sequence[float], periods_per_year: float = 252.0) -> float:
    if len(equity) < 3:
        return 0.0
    rets = np.diff(np.array(equity, dtype=np.float64)) / np.clip(
        np.array(equity[:-1], dtype=np.float64), 1e-12, None
    )
    std = float(np.std(rets))
    if std < 1e-12:
        return 0.0
    return float(np.mean(rets) / std * np.sqrt(periods_per_year))


def _win_rate(trades: Sequence[BacktestTrade], bars: Sequence[BacktestBar]) -> float:
    pairs = []
    i = 0
    while i < len(trades) - 1:
        if trades[i].side == "buy" and trades[i + 1].side == "sell":
            ret = trades[i + 1].price / trades[i].price - 1.0
            pairs.append(ret > 0)
            i += 2
        else:
            i += 1
    if not pairs:
        return 0.0
    return float(mean_bool(pairs))


def mean_bool(values: Sequence[bool]) -> float:
    return sum(1.0 for v in values if v) / len(values)


def bars_from_closes(
    closes: Sequence[float],
    start: Optional[datetime] = None,
) -> List[BacktestBar]:
    """Helper to synthesize OHLC bars from close series for unit tests."""
    from datetime import timedelta, timezone

    start = start or datetime(2024, 1, 2, tzinfo=timezone.utc)
    bars: List[BacktestBar] = []
    for i, close in enumerate(closes):
        bars.append(
            BacktestBar(
                timestamp=start + timedelta(days=i),
                open=close * 0.999,
                high=close * 1.005,
                low=close * 0.995,
                close=float(close),
                volume=1_000_000,
            )
        )
    return bars
