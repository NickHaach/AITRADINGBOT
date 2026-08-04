from __future__ import annotations
"""Mock news feed for local development and tests."""

from datetime import datetime, timedelta, timezone

from news_intelligence.domain.ports import RawNewsItem


class MockNewsFeed:
    """Deterministic synthetic feed covering multiple news categories."""

    name = "mock"

    def __init__(self) -> None:
        self._seeded = self._build_corpus()

    async def fetch_since(
        self, since: datetime | None = None, limit: int = 50
    ) -> list[RawNewsItem]:
        items = self._seeded
        if since is not None:
            # normalize naive/aware comparison
            since_aware = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
            items = [i for i in items if i.published_at >= since_aware]
        return items[:limit]

    def _build_corpus(self) -> list[RawNewsItem]:
        now = datetime.now(timezone.utc)
        stories = [
            (
                "fed-rates-1",
                "Federal Reserve signals higher-for-longer interest rates",
                "The Federal Reserve indicated it may keep interest rates elevated as inflation "
                "remains sticky. Bond yields surged while bank stocks mixed.",
                "financial",
            ),
            (
                "oil-opec-2",
                "OPEC+ discusses further oil production cuts amid Middle East tensions",
                "Crude oil prices jumped after OPEC members considered additional cuts. "
                "Energy and shipping markets reacted sharply.",
                "energy",
            ),
            (
                "ukraine-3",
                "Breaking: New sanctions package targets Russian energy exports",
                "Western governments announced fresh sanctions on Russia following continued "
                "conflict in Ukraine. Defense contractors and gold markets in focus.",
                "geopolitical",
            ),
            (
                "nvidia-ai-4",
                "NVIDIA beats earnings as AI chip demand remains strong",
                "NVIDIA reported record revenue driven by data center AI accelerators. "
                "Technology sector rallied on the upgrade cycle outlook.",
                "technology",
            ),
            (
                "crypto-5",
                "Bitcoin plunges on regulatory crackdown fears",
                "Crypto markets sold off after reports of tighter stablecoin rules. "
                "Ethereum and related tokens followed bitcoin lower.",
                "crypto",
            ),
            (
                "pharma-6",
                "Pfizer announces positive clinical trial results for new drug",
                "Pfizer said late-stage trial data showed strong efficacy. Healthcare "
                "investors cheered the breakthrough opportunity.",
                "healthcare",
            ),
            (
                "defense-7",
                "NATO allies increase defense spending commitments",
                "European governments pledged higher military budgets. Lockheed and "
                "Raytheon shares rose on expected contract flow.",
                "defense",
            ),
            (
                "china-tariff-8",
                "US and China escalate tariff threats on semiconductors",
                "Trade tensions intensified as new tariff proposals targeted chip supply "
                "chains between the United States and China.",
                "geopolitical",
            ),
        ]
        items: list[RawNewsItem] = []
        for idx, (ext_id, title, body, _tag) in enumerate(stories):
            items.append(
                RawNewsItem(
                    external_id=ext_id,
                    source="mock",
                    title=title,
                    body=body,
                    url=f"https://example.com/news/{ext_id}",
                    published_at=now - timedelta(minutes=idx * 15),
                    language="en",
                    raw_metadata={"fixture": True},
                )
            )
        return items
