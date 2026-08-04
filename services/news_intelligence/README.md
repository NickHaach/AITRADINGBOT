# News Intelligence Engine

Ingest → dedupe → classify → embed → persist → publish.

## Run locally

```bash
source .venv/bin/activate
export PYTHONPATH=packages/shared/src:services/news_intelligence/src
uvicorn news_intelligence.api.main:app --reload --port 8001
```

## Endpoints

- `GET /health`
- `POST /v1/news/ingest`
- `GET /v1/news`
- `GET /v1/news/{id}`
- `GET /v1/news/search/semantic?q=`

## Adapters

| Adapter | When used |
|---------|-----------|
| `MockNewsFeed` | Default (`USE_MOCK_NEWS=true`) |
| `NewsApiFeed` | When `NEWSAPI_KEY` set and mock disabled |
| `InMemoryEmbeddingStore` | Local / tests |
| `QdrantEmbeddingStore` | Production vector search |
| `LexiconNewsClassifier` | Offline deterministic classification |

Swap classifiers/embeddings via `ClassifierPort` / `EmbeddingPort` without touching the ingest use case.
