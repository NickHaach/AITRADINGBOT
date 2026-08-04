# Market Data Engine

Fetches OHLCV, derives volatility / liquidity / trend features, exposes HTTP API.

## Run

```bash
source .venv/bin/activate
export PYTHONPATH=packages/shared/src:services/market_data/src
uvicorn market_data.api.main:app --reload --port 8002
```

## Endpoints

- `GET /health`
- `POST /v1/market/refresh?tickers=AAPL,NVDA`
- `POST /v1/market/{ticker}/refresh`
- `GET /v1/market/{ticker}/features`
- `GET /v1/market/{ticker}/bars`
- `GET /v1/market/{ticker}/quote`
- `GET /v1/market/tickers`

## Adapters

| Adapter | When |
|---------|------|
| `MockMarketDataProvider` | Default (`USE_MOCK_MARKET_DATA=true`) |
| `PolygonMarketDataProvider` | `POLYGON_API_KEY` set and mock disabled |
