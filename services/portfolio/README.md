# Portfolio Manager / Desk API

Tracks cash, equity, exposure, and paper performance. The desk API runs a
seeded `TradingPipeline` cycle on boot and exposes the live book.

```bash
uvicorn portfolio.api.main:app --port 8008
```

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v1/portfolio` | Latest cash / equity / positions |
| GET | `/v1/portfolio/history` | Snapshot history |
| POST | `/v1/portfolio/run` | Run another paper cycle |
| GET | `/v1/portfolio/recommendations` | Recent non-HOLD signals |
