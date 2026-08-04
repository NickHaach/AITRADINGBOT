"""In-memory announcement repository with source/external_id dedupe."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from ai_trading_shared.domain.entities import Announcement


class InMemoryAnnouncementRepository:
    def __init__(self) -> None:
        self._items: Dict[UUID, Announcement] = {}
        self._seen: Set[Tuple[str, str]] = set()

    async def upsert(self, announcement: Announcement, *, external_id: str = "") -> Announcement:
        self._items[announcement.id] = announcement
        if external_id:
            self._seen.add((announcement.source, external_id))
        return announcement

    async def get(self, announcement_id: UUID) -> Optional[Announcement]:
        return self._items.get(announcement_id)

    async def list_recent(
        self, limit: int = 50, ticker: Optional[str] = None
    ) -> List[Announcement]:
        items = list(self._items.values())
        if ticker:
            items = [a for a in items if a.company_ticker.upper() == ticker.upper()]
        items.sort(key=lambda a: a.filed_at, reverse=True)
        return items[:limit]

    async def exists(self, source: str, external_id: str) -> bool:
        return (source, external_id) in self._seen
