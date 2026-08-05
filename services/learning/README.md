# Learning Engine

Tracks closed-trade outcomes, measures direction accuracy / Brier score, and
emits model improvement suggestions. Supports optional SQL dual-write, rolling
eval windows, Celery beat jobs, and model registry promotion.

```bash
# API
uvicorn learning.api.main:app --port 8007

# Worker + beat (rolling 7-day eval every 10 minutes)
celery -A learning.workers.celery_app.celery_app worker --beat --loglevel=INFO
```

## Key endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST | `/v1/learning/outcomes` | Record closed trade (dual-writes when `ENABLE_SQL_PERSISTENCE=true`) |
| GET | `/v1/learning/report?window_days=7` | Rolling accuracy report |
| POST | `/v1/models/register` | Register model version + metrics |
| POST | `/v1/models/{name}/versions/{version}/promote` | Flip production flag |
| POST | `/v1/models/auto-promote` | Promote when sample≥30, dir_acc≥0.55, Brier≤0.25 |

Promotion is gated — live trading still requires separate execution flags.

Paper fills open lots that close after `horizon_days` simulated cycles and
dual-write into Learning. Calibration temperature is refreshed from outcomes
(`POST /v1/learning/calibration/refresh`, Celery every 15m).
