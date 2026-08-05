# Module roadmap

## Completed

| Module | Status |
|--------|--------|
| Shared kernel / News / API / Risk / Paper execution | Done |
| Market / Announcements / Macro / Geo / Sentiment | Done |
| Prediction + trading pipeline | Done |
| Learning + Backtesting + Alpaca adapter + Dashboard | Done |
| **Postgres persistence repos** (market/predictions/outcomes) | Done |
| **Knowledge graph** (news↔filings↔tickers↔geo) | Done |
| **Trainable GBM direction model** (sklearn / optional XGBoost) | Done |

## Next increments

1. Wire services to Postgres repos in production Docker profiles
2. TradingView chart widgets + live WebSocket market stream
3. Celery beat jobs for continuous learning evaluation windows
4. Persist knowledge graph nodes/edges to Postgres (`graph_nodes` / `graph_edges`)
5. Online model registry promotion from training metrics

Each increment must ship with unit tests, module README, and mock adapters.
