"""Intelligence gatherer — offline channels always populate."""

from __future__ import annotations

import pytest

from execution.intelligence import gather_intelligence


@pytest.mark.asyncio
async def test_gather_intelligence_offline_seeds():
    bundle = await gather_intelligence(
        ["AAPL", "MSFT", "NVDA"],
        news_url="http://127.0.0.1:9",
        announcements_url="http://127.0.0.1:9",
        include_web=False,
    )
    assert "forum_seed" in bundle.sources_used
    assert "analyst_notes_seed" in bundle.sources_used
    assert "AAPL" in bundle.social_by_ticker
    assert "NVDA" in bundle.analyst_by_ticker
    summary = bundle.summary()
    assert summary["social_count"] >= 1
    assert "AAPL" in summary["tickers_with_social"]
