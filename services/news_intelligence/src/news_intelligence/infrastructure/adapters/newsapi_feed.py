from __future__ import annotations
"""Optional NewsAPI.org adapter. Requires NEWSAPI_KEY and licensed use."""

from datetime import datetime

import httpx

from ai_trading_shared.utils.logging import get_logger
from news_intelligence.domain.ports import RawNewsItem

logger = get_logger(__name__)


class NewsApiFeed:
    """Fetches top business headlines from NewsAPI when a key is configured."""

    name = "newsapi"

    def __init__(self, api_key: str, base_url: str = "https://newsapi.org/v2") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    async def fetch_since(
        self, since: datetime | None = None, limit: int = 50
    ) -> list[RawNewsItem]:
        params: dict[str, str | int] = {
            "category": "business",
            "language": "en",
            "pageSize": min(limit, 100),
            "apiKey": self._api_key,
        }
        if since is not None:
            params["from"] = since.strftime("%Y-%m-%dT%H:%M:%S")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self._base_url}/top-headlines", params=params)
            response.raise_for_status()
            data = response.json()

        items: list[RawNewsItem] = []
        for article in data.get("articles", []):
            title = article.get("title") or ""
            body = article.get("description") or article.get("content") or title
            url = article.get("url")
            published = article.get("publishedAt")
            if not title or not published:
                continue
            published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            external_id = url or f"{title}:{published}"
            items.append(
                RawNewsItem(
                    external_id=external_id[:255],
                    source="newsapi",
                    title=title,
                    body=body,
                    url=url,
                    published_at=published_at,
                    language="en",
                    raw_metadata={"provider": "newsapi"},
                )
            )
        logger.info("newsapi_fetched", count=len(items))
        return items
