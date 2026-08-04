"""Celery worker for scheduled news ingestion."""

from celery import Celery

from ai_trading_shared.config import get_settings

settings = get_settings()

celery_app = Celery(
    "news_intelligence",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "ingest-news-every-2-minutes": {
            "task": "news_intelligence.workers.tasks.ingest_news_task",
            "schedule": 120.0,
        },
    },
)
