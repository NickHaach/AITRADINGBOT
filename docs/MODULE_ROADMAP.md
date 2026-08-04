# Module roadmap

## Completed

| Module | Status |
|--------|--------|
| Shared kernel | Done |
| News Intelligence | Done |
| API Gateway | Done |
| Risk / Execution (paper) / Portfolio / LLM | Done |
| Market Data / Announcements / Macro / Geo / Sentiment | Done |
| Prediction (calibrated ensemble) + trading pipeline | Done |
| **Learning Engine** | Done (outcomes, accuracy, suggestions) |
| **Backtesting Engine** | Done (OHLCV+news replay, Sharpe/DD/win rate) |
| **Alpaca broker adapter** | Done (dual-flag gated; paper default) |
| **Dashboard polish** | Done (positions, risk, explainability, filings) |

## Next increments

1. Persist market/announcement/prediction/outcome rows to Postgres
2. Knowledge graph linking news ↔ filings ↔ tickers ↔ geo events
3. Richer ML models (XGBoost/LightGBM) trained on stored features
4. TradingView chart widgets + live WebSocket market stream
5. Celery beat jobs for continuous learning evaluation windows

Each increment must ship with unit tests, module README, and mock adapters.
