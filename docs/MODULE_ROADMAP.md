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
| **Shared calibration via Redis** (memory fallback) | Done |
| **GBM joblib artifacts + production load** | Done |
| **JWT portfolio proxy** on API gateway | Done |
| **Aether Desk login** + authed book/recs | Done |
| **GBM train from real outcome feature rows** | Done |
| **HttpOnly session cookies** + cookie/Bearer dual auth | Done |
| **Paper Run cycle** button (trader/admin) | Done |

## Next increments

1. TradingView lightweight widgets (optional upgrade over Recharts tape)
2. Object storage (S3) behind the same artifact URI interface
3. Lock news/market/announcements behind JWT once desk auth is default
4. Session refresh on 401 (silent cookie rotation)
5. Multi-ticker cycle picker UI

Each increment must ship with unit tests, module README, and mock adapters.
