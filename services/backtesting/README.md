# Backtesting Engine

Replays OHLCV (+ optional news sentiment) through a long-only momentum strategy.
Reports total return, max drawdown, Sharpe, and win rate.

```bash
uvicorn backtesting.api.main:app --port 8008
```
