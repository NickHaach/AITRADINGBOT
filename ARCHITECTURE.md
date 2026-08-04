# Architecture Decision Record

## Purpose

Personal AI investment assistant that ingests multi-source market intelligence,
reasons with ML + LLMs, enforces risk gates, and executes only after validation.
Default mode is **paper trading**. Live broker execution requires explicit config
and RBAC-authorized enablement.

## Core principles

1. **Safety first** — Risk Engine is a hard gate. No order reaches a broker without
   passing configured risk rules. Kill-switch and daily loss limits are first-class.
2. **Adapter-driven I/O** — News feeds, brokers, LLMs, and market data are ports
   with swappable adapters (live, mock, paper). Licensing/API terms are respected
   via configurable, authenticated adapters only.
3. **Event-driven pipeline** — Producers emit domain events to Redis Streams;
   Celery workers consume and fan out. Services stay loosely coupled.
4. **Clean architecture** — Domain has no infra imports. Application orchestrates
   use cases. Infrastructure implements ports. API is a thin transport layer.
5. **Explainability** — Every signal/trade stores structured rationale JSON
   (what / why / horizon / confidence / risks).
6. **Incremental deployability** — Each engine is an independently runnable service
   sharing `ai_trading_shared`. Kubernetes-ready, Docker Compose for local.

## Topology

```
                    ┌─────────────────┐
                    │  Next.js Dash   │
                    └────────┬────────┘
                             │ HTTPS / JWT
                    ┌────────▼────────┐
                    │   API Gateway   │
                    └───┬─────┬───┬───┘
                        │     │   │
        ┌───────────────┘     │   └───────────────┐
        ▼                     ▼                   ▼
  Intelligence         Decision Layer        Execution
  (news, macro,        (prediction,          (risk →
   geo, sentiment,      LLM reasoning,        execution →
   announcements,       learning,             portfolio)
   market data)         backtesting)
        │                     │                   │
        └──────────┬──────────┴─────────┬─────────┘
                   ▼                    ▼
            PostgreSQL + Redis    Qdrant (vectors)
```

## Data stores

| Store      | Role                                      |
|------------|-------------------------------------------|
| PostgreSQL | System of record (entities, trades, audit)|
| Redis      | Cache, rate limits, Celery broker, streams|
| Qdrant     | News/announcement embeddings + RAG search |

## Module build order

0. Shared kernel + infra (this foundation)
1. News Intelligence Engine
2. Market Data Engine
3. Company Announcement Engine
4. Macro + Geopolitical + Sentiment
5. Prediction + LLM Reasoning
6. Risk + Execution (paper) + Portfolio
7. Learning + Backtesting
8. Dashboard polish + live broker adapters

## Security baseline

- JWT access + refresh tokens; OAuth providers pluggable
- RBAC roles: `viewer`, `analyst`, `trader`, `admin`
- Secrets via env / Docker secrets (never committed)
- Rate limiting at gateway
- Audit log for auth, config changes, and all order attempts
- Input validation with Pydantic everywhere
- TLS termination at ingress (prod)

## Non-goals (v1)

- High-frequency market making
- Guaranteed alpha
- Scraping paywalled sources without licensed APIs
- Unsupervised live capital deployment
