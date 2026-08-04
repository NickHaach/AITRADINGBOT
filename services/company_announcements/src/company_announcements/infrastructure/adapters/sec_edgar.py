"""SEC EDGAR recent filings adapter (company tickers via CIK map).

Uses the public SEC submissions/data endpoints. Respect SEC fair-access
guidelines (User-Agent identifying the application).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

import httpx

from ai_trading_shared.utils.logging import get_logger
from company_announcements.domain.ports import RawFiling

logger = get_logger(__name__)

# Small CIK map for bootstrapping; extend via config/DB in production
DEFAULT_CIKS: Dict[str, str] = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
    "XOM": "0000034088",
    "JPM": "0000019617",
}


class SecEdgarFeed:
    name = "sec_edgar"

    def __init__(
        self,
        user_agent: str = "AITradingPlatform research@localhost",
        cik_map: Dict[str, str] | None = None,
        base_url: str = "https://data.sec.gov",
    ) -> None:
        self._user_agent = user_agent
        self._cik_map = cik_map or DEFAULT_CIKS
        self._base_url = base_url.rstrip("/")

    async def fetch_recent(self, limit: int = 50) -> List[RawFiling]:
        filings: List[RawFiling] = []
        headers = {"User-Agent": self._user_agent, "Accept-Encoding": "gzip, deflate"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            for ticker, cik in self._cik_map.items():
                url = f"{self._base_url}/submissions/CIK{cik}.json"
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                except Exception:
                    logger.exception("sec_edgar_fetch_failed", ticker=ticker)
                    continue
                recent = data.get("filings", {}).get("recent", {})
                forms = recent.get("form", [])
                accessions = recent.get("accessionNumber", [])
                dates = recent.get("filingDate", [])
                primaries = recent.get("primaryDocument", [])
                for i, form in enumerate(forms[: max(1, limit // max(len(self._cik_map), 1))]):
                    if form not in {"8-K", "10-Q", "10-K", "4", "6-K"}:
                        continue
                    accession = accessions[i].replace("-", "")
                    filed = datetime.strptime(dates[i], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    primary = primaries[i] if i < len(primaries) else ""
                    title = f"{ticker} {form} filed {dates[i]}"
                    body = (
                        f"SEC {form} filing for {ticker}. Accession {accessions[i]}. "
                        f"Primary document: {primary}."
                    )
                    filings.append(
                        RawFiling(
                            external_id=f"{ticker}-{accessions[i]}",
                            company_ticker=ticker,
                            filing_type=form,
                            title=title,
                            body=body,
                            source="sec_edgar",
                            filed_at=filed,
                            raw_metadata={"cik": cik, "accession": accession},
                        )
                    )
        filings.sort(key=lambda f: f.filed_at, reverse=True)
        logger.info("sec_edgar_fetched", count=len(filings[:limit]))
        return filings[:limit]
