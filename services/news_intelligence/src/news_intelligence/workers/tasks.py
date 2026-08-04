"""Celery tasks for news intelligence."""

import asyncio

from news_intelligence.api.main import build_ingest_service
from news_intelligence.workers.celery_app import celery_app
from ai_trading_shared.config import get_settings
from ai_trading_shared.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


@celery_app.task(name="news_intelligence.workers.tasks.ingest_news_task")
def ingest_news_task() -> dict:
    settings = get_settings()
    configure_logging(settings.log_level)
    service = build_ingest_service(settings)
    articles = asyncio.run(service.run_cycle())
    logger.info("celery_ingest_done", count=len(articles))
    return {"ingested": len(articles)}
