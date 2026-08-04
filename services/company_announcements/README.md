# Company Announcement Engine

Ingests earnings / filings / M&A / buybacks, extracts financials, scores impact.

## Run

```bash
source .venv/bin/activate
export PYTHONPATH=packages/shared/src:services/company_announcements/src
uvicorn company_announcements.api.main:app --reload --port 8003
```

## Endpoints

- `GET /health`
- `POST /v1/announcements/ingest`
- `GET /v1/announcements?ticker=NVDA`
- `GET /v1/announcements/{id}`

## Adapters

| Adapter | Notes |
|---------|-------|
| `MockFilingFeed` | Default offline corpus |
| `SecEdgarFeed` | Live SEC submissions API (requires network + User-Agent) |
| `LexiconAnnouncementExtractor` | Deterministic NLP; swap for LLM extractor later |
