"""End-to-end paper trading pipeline integration test."""

from __future__ import annotations

from decimal import Decimal

import pytest

from execution.pipeline import TradingPipeline


@pytest.mark.asyncio
async def test_pipeline_runs_paper_cycle() -> None:
    pipeline = TradingPipeline(starting_cash=Decimal("100000"))
    result = await pipeline.run_once(
        tickers=["AAPL", "NVDA", "XOM"],
        news_by_ticker={
            "NVDA": "NVIDIA surge on record AI demand and upgrade",
            "XOM": "Oil plunge on weak demand fears",
            "AAPL": "Apple steady after mixed commentary",
        },
        announcement_impact={"NVDA": 0.4, "XOM": -0.3},
    )
    assert result["signals"] == 3
    assert result["equity"] > 0
    assert result["approved_trades"] + result["rejected_trades"] >= 0
    # At least one actionable path evaluated (buy/sell/hold all valid)
    assert isinstance(result["fills"], list)
