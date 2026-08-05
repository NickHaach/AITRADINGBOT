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
| **Learning dual-write + rolling `window_days` eval** | Done |
| **Celery beat learning eval** (`evaluate_window_task` every 10m) | Done |
| **Model registry register / promote / auto-promote** | Done |
| **Prediction dual-write in trading pipeline** | Done |
| **Portfolio desk API** (`:8008`) + live dashboard book | Done |
| **Paper lot close → Learning outcomes** (sim horizon) | Done |
| **Online temperature calibration refresh** (API + Celery) | Done |

## Next increments

1. Auth-gated gateway proxy for portfolio (JWT) once dashboard login lands
2. TradingView lightweight widgets (optional upgrade over Recharts tape)
3. Persist GBM artifacts to object storage and load production models at runtime
4. Share calibration temperature across services via Redis/registry
5. Dashboard login + authenticated portfolio fetches

Each increment must ship with unit tests, module README, and mock adapters.
