# AI Trading Platform

Production-oriented personal investment assistant: multi-source intelligence →
ML/LLM reasoning → risk-gated execution → continuous learning.

> **Default: paper trading only.** Live brokers stay disabled until you
> explicitly enable them and pass risk configuration.

## Connect a broker (Alpaca)

From the desk (signed in as trader/admin):

1. Open [Alpaca paper](https://app.alpaca.markets/paper/dashboard/overview) and create Paper API keys.
2. Paste them into the **Broker** panel → **Connect paper**.
3. Hit **Run cycle** — approved trades submit to Alpaca paper.

Or via `.env` (requires portfolio restart):

```bash
BROKER_ALPACA_API_KEY=...
BROKER_ALPACA_SECRET_KEY=...
BROKER_ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

**Real money** additionally requires `EXECUTION_MODE=live`, `ENABLE_LIVE_TRADING=true`, and live base URL (dual confirmation).

## Local desk (no Docker)

```bash
make run-desk          # api, news, market, filings, portfolio
cd apps/dashboard && npm run dev
```

## Quick start

```bash
cp .env.example .env
make bootstrap   # install deps, start infra
make migrate
make up          # all services via docker-compose
make test
```

Dashboard: http://localhost:3000  
API docs:  http://localhost:8000/docs

## Stack

- **Backend:** Python 3.9+ (3.12 recommended), FastAPI, AsyncIO, Celery, PostgreSQL, Redis, Qdrant
- **AI/ML:** OpenAI / local LLM adapters, Sentence Transformers, scikit-learn, XGBoost
- **Frontend:** Next.js, React, Tailwind, Recharts
- **Ops:** Docker Compose, GitHub Actions, Prometheus, Grafana

Default admin (dev only): `admin@local.dev` / `ChangeMeAdmin123!`

## Services

| Service | Responsibility |
|---------|----------------|
| `api_gateway` | Auth, RBAC, public HTTP API |
| `news_intelligence` | Ingest, normalize, classify, embed news |
| `company_announcements` | Filings & earnings extraction |
| `geopolitical` | Conflict / sanctions / trade impact |
| `macro` | Economic calendar & indicators |
| `sentiment` | Multi-source sentiment scores |
| `market_data` | Prices, volume, volatility streams |
| `prediction` | Ensemble forecasts |
| `llm_reasoning` | Structured decision JSON |
| `risk` | Hard risk gates & sizing |
| `execution` | Broker adapters (paper / live) |
| `portfolio` | Positions, PnL, exposure |
| `learning` | Outcome feedback loops |
| `backtesting` | Historical replay |

See [ARCHITECTURE.md](./ARCHITECTURE.md) for design decisions and build order.

## Development

```bash
make lint
make test
make test-news          # news intelligence only
make logs SVC=news_intelligence
```

## License

Private / personal use. Respect all data-provider API and licensing terms.
