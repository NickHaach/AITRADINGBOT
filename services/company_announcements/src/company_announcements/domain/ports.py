"""Announcement domain ports."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Protocol
from uuid import UUID

from pydantic import Field

from ai_trading_shared.domain.entities import Announcement
from ai_trading_shared.domain.enums import DomainModel


class RawFiling(DomainModel):
    external_id: str
    company_ticker: str
    filing_type: str
    title: str
    body: str
    source: str
    filed_at: datetime
    raw_metadata: dict = Field(default_factory=dict)


class FilingFeedPort(Protocol):
    name: str

    async def fetch_recent(self, limit: int = 50) -> List[RawFiling]:
        ...


class AnnouncementExtractorPort(Protocol):
    async def extract(self, filing: RawFiling) -> Announcement:
        ...


class AnnouncementRepositoryPort(Protocol):
    async def upsert(self, announcement: Announcement, *, external_id: str) -> Announcement:
        ...

    async def get(self, announcement_id: UUID) -> Optional[Announcement]:
        ...

    async def list_recent(
        self, limit: int = 50, ticker: Optional[str] = None
    ) -> List[Announcement]:
        ...

    async def exists(self, source: str, external_id: str) -> bool:
        ...
