# Knowledge Graph

Links news, filings, tickers, sectors, countries, and geopolitical events.

```bash
uvicorn knowledge_graph.engine:app --port 8009
```

## Useful calls

- `POST /v1/graph/news`
- `POST /v1/graph/filings`
- `POST /v1/graph/geo`
- `GET /v1/graph/related-tickers?ticker=NVDA`
- `GET /v1/graph/neighbors?node_type=ticker&key=NVDA`
