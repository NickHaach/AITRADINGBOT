"""Company announcement unit tests."""

from __future__ import annotations

import pytest

from company_announcements.application.extractor import LexiconAnnouncementExtractor
from company_announcements.application.ingest import AnnouncementIngestService
from company_announcements.domain.ports import RawFiling
from company_announcements.infrastructure.adapters.mock_feed import MockFilingFeed
from company_announcements.infrastructure.repositories.memory import InMemoryAnnouncementRepository
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_extractor_earnings_beat() -> None:
    filing = RawFiling(
        external_id="t1",
        company_ticker="NVDA",
        filing_type="earnings",
        title="NVIDIA earnings beat; raises guidance",
        body="Revenue of $30.0 billion and EPS of $0.68 above expectations. Operating margin of 62%.",
        source="test",
        filed_at=datetime.now(timezone.utc),
    )
    result = await LexiconAnnouncementExtractor().extract(filing)
    assert result.company_ticker == "NVDA"
    assert result.revenue is not None and result.revenue > 0
    assert result.eps is not None
    assert result.margins is not None
    assert result.impact_score > 0
    assert result.forward_guidance is not None


@pytest.mark.asyncio
async def test_extractor_adverse_8k() -> None:
    filing = RawFiling(
        external_id="t2",
        company_ticker="XOM",
        filing_type="8-K",
        title="Impairment and restructuring",
        body="Company disclosed impairment and restructuring amid weak demand and inflation risk.",
        source="test",
        filed_at=datetime.now(timezone.utc),
    )
    result = await LexiconAnnouncementExtractor().extract(filing)
    assert result.impact_score < 0
    assert "inflation" in result.risks or "risk" in result.risks


@pytest.mark.asyncio
async def test_ingest_deduplicates() -> None:
    service = AnnouncementIngestService(
        feeds=[MockFilingFeed()],
        extractor=LexiconAnnouncementExtractor(),
        repository=InMemoryAnnouncementRepository(),
    )
    first = await service.run_cycle()
    second = await service.run_cycle()
    assert len(first) >= 4
    assert len(second) == 0
    by_ticker = await service.list_recent(ticker="NVDA")
    assert len(by_ticker) >= 1
