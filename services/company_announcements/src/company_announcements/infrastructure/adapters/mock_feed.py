"""Mock corporate filings covering earnings, M&A, buybacks, guidance."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from company_announcements.domain.ports import RawFiling


class MockFilingFeed:
    name = "mock_filings"

    async def fetch_recent(self, limit: int = 50) -> List[RawFiling]:
        now = datetime.now(timezone.utc)
        corpus = [
            RawFiling(
                external_id="nvda-earn-1",
                company_ticker="NVDA",
                filing_type="earnings",
                title="NVIDIA reports Q2 earnings beat; raises guidance",
                body=(
                    "NVIDIA announced revenue of $30.0 billion and EPS of $0.68, "
                    "both above expectations. Operating margin of 62%. Management "
                    "raised guidance citing strong demand for AI accelerators and "
                    "new partnership opportunities in the cloud pipeline."
                ),
                source="mock",
                filed_at=now - timedelta(hours=2),
            ),
            RawFiling(
                external_id="xom-8k-1",
                company_ticker="XOM",
                filing_type="8-K",
                title="Exxon Mobil 8-K: impairment and restructuring update",
                body=(
                    "Exxon Mobil disclosed an impairment charge and restructuring "
                    "plan amid weak demand in certain downstream markets. "
                    "Management cited inflation and supply chain risk."
                ),
                source="mock",
                filed_at=now - timedelta(hours=5),
            ),
            RawFiling(
                external_id="msft-buyback-1",
                company_ticker="MSFT",
                filing_type="buyback",
                title="Microsoft authorizes $60 billion share repurchase",
                body=(
                    "Microsoft announced a $60 billion share buyback program and "
                    "a dividend increase, reflecting record cash generation."
                ),
                source="mock",
                filed_at=now - timedelta(hours=8),
            ),
            RawFiling(
                external_id="aapl-maq-1",
                company_ticker="AAPL",
                filing_type="M&A",
                title="Apple announces acquisition of AI chip startup",
                body=(
                    "Apple completed an acquisition of a semiconductor startup to "
                    "expand its AI pipeline. Opportunities include market share "
                    "gains; risks include regulatory review and integration."
                ),
                source="mock",
                filed_at=now - timedelta(hours=12),
            ),
            RawFiling(
                external_id="bhp-asx-1",
                company_ticker="BHP",
                filing_type="ASX",
                title="BHP ASX announcement: production guidance cut",
                body=(
                    "BHP cut guidance for iron ore shipments after weather "
                    "disruption. Management flagged supply chain uncertainty."
                ),
                source="mock",
                filed_at=now - timedelta(hours=16),
            ),
            RawFiling(
                external_id="jpm-10q-1",
                company_ticker="JPM",
                filing_type="10-Q",
                title="JPMorgan 10-Q: net interest income beat",
                body=(
                    "JPMorgan reported revenue of $42.5 billion with net interest "
                    "income above expectations. Credit quality remained stable; "
                    "management reaffirmed guidance."
                ),
                source="mock",
                filed_at=now - timedelta(hours=20),
            ),
        ]
        return corpus[:limit]
