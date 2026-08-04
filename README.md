# AI Trading Platform

Production-oriented personal investment assistant: multi-source intelligence →
ML/LLM reasoning → risk-gated execution → continuous learning.

> **Default: paper trading only.** Live brokers stay disabled until you
> explicitly enable them and pass risk configuration.

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
