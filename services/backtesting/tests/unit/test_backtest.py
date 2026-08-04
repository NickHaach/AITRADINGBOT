"""Backtesting unit tests."""

from __future__ import annotations

from datetime import datetime, timezone

from backtesting.application.engine import BacktestEngine, MomentumNewsStrategy, bars_from_closes
from backtesting.domain.models import NewsEvent


def test_momentum_backtest_runs() -> None:
    # upward trend then flat
    closes = [100 + i * 0.5 for i in range(40)] + [120 - i * 0.2 for i in range(20)]
    bars = bars_from_closes(closes)
    engine = BacktestEngine(initial_cash=100_000)
    result = engine.run(ticker="SPY", bars=bars, strategy=MomentumNewsStrategy(lookback=5))
    assert result.trade_count >= 1
    assert result.final_equity > 0
    assert 0 <= result.max_drawdown <= 1
    assert result.ticker == "SPY"


def test_news_blocks_entry_on_bad_sentiment() -> None:
    closes = [100 + i for i in range(30)]
    bars = bars_from_closes(closes)
    # strongly negative sentiment every day
    news = [
        NewsEvent(
            timestamp=b.timestamp,
            ticker="AAPL",
            sentiment_score=-0.9,
            headline="crash fears",
        )
        for b in bars
    ]
    engine = BacktestEngine()
    result = engine.run(
        ticker="AAPL",
        bars=bars,
        strategy=MomentumNewsStrategy(lookback=5, sentiment_floor=-0.4),
        news=news,
    )
    assert result.trade_count == 0
