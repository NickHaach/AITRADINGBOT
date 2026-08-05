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
| **Market dual-write** (memory + optional SQL via `ENABLE_SQL_PERSISTENCE`) | Done |
| **Graph SQL persist/load** (`POST /v1/graph/persist` · `/load`) | Done |
| **Live market WebSocket** (`/v1/market/stream`) + dashboard tape chart | Done |

## Next increments

1. Celery beat jobs for continuous learning evaluation windows
2. Online model registry promotion from training metrics
3. TradingView lightweight widgets (optional upgrade over Recharts tape)
4. Wire remaining services (learning outcomes, predictions) to dual-write in Docker
5. Auth-gated dashboard portfolio API (replace demo book)

Each increment must ship with unit tests, module README, and mock adapters.
