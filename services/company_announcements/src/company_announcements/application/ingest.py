"""Announcement ingest use case."""

from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID

from ai_trading_shared.domain.entities import Announcement
from ai_trading_shared.events import STREAM_ANNOUNCEMENTS, AnnouncementParsed
from ai_trading_shared.infrastructure.redis_bus import RedisEventBus
from ai_trading_shared.utils.logging import get_logger
from company_announcements.domain.ports import (
    AnnouncementExtractorPort,
    AnnouncementRepositoryPort,
    FilingFeedPort,
)

logger = get_logger(__name__)


class AnnouncementIngestService:
    def __init__(
        self,
        feeds: Sequence[FilingFeedPort],
        extractor: AnnouncementExtractorPort,
        repository: AnnouncementRepositoryPort,
        event_bus: Optional[RedisEventBus] = None,
    ) -> None:
        self._feeds = list(feeds)
        self._extractor = extractor
        self._repo = repository
        self._bus = event_bus

    async def run_cycle(self, limit_per_feed: int = 50) -> List[Announcement]:
        ingested: List[Announcement] = []
        for feed in self._feeds:
            try:
                filings = await feed.fetch_recent(limit=limit_per_feed)
            except Exception:
                logger.exception("filing_feed_failed", feed=feed.name)
                continue
            for filing in filings:
                if await self._repo.exists(filing.source, filing.external_id):
                    continue
                announcement = await self._extractor.extract(filing)
                saved = await self._repo.upsert(announcement, external_id=filing.external_id)
                if self._bus is not None:
                    await self._bus.publish(
                        STREAM_ANNOUNCEMENTS,
                        AnnouncementParsed(
                            payload={
                                "id": str(saved.id),
                                "ticker": saved.company_ticker,
                                "filing_type": saved.filing_type,
                                "impact_score": saved.impact_score,
                            }
                        ),
                    )
                ingested.append(saved)
        logger.info("announcements_ingested", count=len(ingested))
        return ingested

    async def list_recent(
        self, limit: int = 50, ticker: Optional[str] = None
    ) -> List[Announcement]:
        return await self._repo.list_recent(limit=limit, ticker=ticker)

    async def get(self, announcement_id: UUID) -> Optional[Announcement]:
        return await self._repo.get(announcement_id)
