"""Multi-source intelligence gatherer for autonomous trade cycles.

Pulls news outlets, filings, social/forum chatter, macro, and geopolitical
context into per-ticker text + impact features for SentimentEngine / predictors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

import httpx

from ai_trading_shared.utils.logging import get_logger

logger = get_logger(__name__)

# Free public RSS outlets (no API key). Failures fall back to local services/mocks.
RSS_OUTLETS = (
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("CNBC Top News", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
)

# Public Reddit JSON (no key). Soft-fail if blocked.
REDDIT_FORUMS = (
    ("reddit_stocks", "https://www.reddit.com/r/stocks/hot.json?limit=20"),
    ("reddit_investing", "https://www.reddit.com/r/investing/hot.json?limit=15"),
    ("reddit_wallstreetbets", "https://www.reddit.com/r/wallstreetbets/hot.json?limit=15"),
)

TICKER_ALIASES = {
    "APPLE": "AAPL",
    "MICROSOFT": "MSFT",
    "NVIDIA": "NVDA",
    "EXXON": "XOM",
    "JPMORGAN": "JPM",
    "JP MORGAN": "JPM",
    "TESLA": "TSLA",
    "AMAZON": "AMZN",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "META": "META",
    "FACEBOOK": "META",
    "BITCOIN": "BTCUSD",
    "ETHEREUM": "ETHUSD",
}

# Seeded social/forum chatter so cycles always have social signal offline.
MOCK_SOCIAL: Dict[str, List[str]] = {
    "AAPL": [
        "r/stocks: Apple services growth looking sticky; AI phone cycle could re-rate multiples.",
        "StockTwits: AAPL accumulation near support, options flow skewed call-heavy.",
    ],
    "MSFT": [
        "r/investing: Azure commentary still the main driver; Copilot attach rates debated.",
        "Forum: MSFT seen as quality compounder into higher-for-longer rates.",
    ],
    "NVDA": [
        "r/wallstreetbets: NVDA demand from hyperscalers still the tape; vol crush risk after run.",
        "Twitter/X finance: data-center GPU lead times normalizing but backlog solid.",
    ],
    "XOM": [
        "Energy board: crude premium from OPEC chatter supporting integrated majors.",
        "r/investing: XOM FCF and buybacks valued more than growth narrative.",
    ],
    "JPM": [
        "Banking forum: NII resilient; credit quality watched but not stressed yet.",
        "r/stocks: JPM preferred mega-bank on capital markets rebound.",
    ],
    "SPY": [
        "Macro thread: soft-landing odds rising; SPY grinding with low realized vol.",
    ],
    "BTCUSD": [
        "Crypto Twitter: BTC holding range; ETF flows mentioned as bid.",
        "r/Bitcoin: risk-on tone after equity rebound.",
    ],
    "ETHUSD": [
        "ETH traders: staking yield vs L2 fee compression debate continues.",
    ],
}

MOCK_ANALYST: Dict[str, str] = {
    "AAPL": "Street note: Maintain overweight; services margin expansion offsets hardware cycles.",
    "MSFT": "Analyst upgrade chatter: AI monetization path clearer than peers.",
    "NVDA": "Consensus: Buy; raise PT on sustained data-center demand.",
    "XOM": "Neutral: oil beta intact; watch OPEC compliance.",
    "JPM": "Overweight: capital markets rebound and fortress balance sheet.",
}


@dataclass
class IntelligenceBundle:
    news_by_ticker: Dict[str, str] = field(default_factory=dict)
    social_by_ticker: Dict[str, str] = field(default_factory=dict)
    analyst_by_ticker: Dict[str, str] = field(default_factory=dict)
    announcement_impact: Dict[str, float] = field(default_factory=dict)
    macro_bias: Dict[str, float] = field(default_factory=dict)
    geo_bias: Dict[str, float] = field(default_factory=dict)
    sources_used: List[str] = field(default_factory=list)
    headlines: List[Dict[str, Any]] = field(default_factory=list)
    social_posts: List[Dict[str, str]] = field(default_factory=list)
    as_of: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def summary(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "sources_used": self.sources_used,
            "tickers_with_news": sorted(self.news_by_ticker.keys()),
            "tickers_with_social": sorted(self.social_by_ticker.keys()),
            "tickers_with_filings": sorted(self.announcement_impact.keys()),
            "headline_count": len(self.headlines),
            "social_count": len(self.social_posts),
            "macro_tickers": sorted(self.macro_bias.keys()),
            "geo_tickers": sorted(self.geo_bias.keys()),
            "sample_headlines": self.headlines[:6],
            "sample_social": self.social_posts[:6],
        }


def _detect_tickers(text: str, universe: List[str]) -> List[str]:
    upper = text.upper()
    hits: List[str] = []
    for ticker in universe:
        if ticker.upper() in upper:
            hits.append(ticker.upper())
    for alias, ticker in TICKER_ALIASES.items():
        if alias in upper and ticker in {t.upper() for t in universe}:
            if ticker not in hits:
                hits.append(ticker)
    return hits


def _append_text(bucket: Dict[str, str], ticker: str, chunk: str) -> None:
    chunk = chunk.strip()
    if not chunk:
        return
    prev = bucket.get(ticker, "")
    bucket[ticker] = f"{prev}\n{chunk}".strip() if prev else chunk


async def _fetch_json(client: httpx.AsyncClient, url: str) -> Optional[Any]:
    try:
        res = await client.get(url, headers={"User-Agent": "AetherDesk/0.1 research"})
        if res.status_code >= 400:
            return None
        return res.json()
    except Exception:
        logger.debug("intel_json_failed", url=url)
        return None


async def _fetch_rss(client: httpx.AsyncClient, name: str, url: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    try:
        res = await client.get(url, headers={"User-Agent": "AetherDesk/0.1 research"})
        if res.status_code >= 400:
            return items
        root = ElementTree.fromstring(res.text)
        for item in root.findall(".//item")[:12]:
            title = (item.findtext("title") or "").strip()
            desc = (item.findtext("description") or "").strip()
            if title:
                items.append({"source": name, "title": title, "body": desc})
    except Exception:
        logger.debug("intel_rss_failed", source=name)
    return items


async def gather_intelligence(
    tickers: List[str],
    *,
    news_url: str = "http://127.0.0.1:8001",
    announcements_url: str = "http://127.0.0.1:8003",
    include_web: bool = True,
) -> IntelligenceBundle:
    """Assemble multi-source context for a trading universe."""
    universe = [t.upper() for t in tickers]
    bundle = IntelligenceBundle()

    # Always include seeded social + analyst so cycles have non-empty channels offline.
    for t in universe:
        for post in MOCK_SOCIAL.get(t, []):
            _append_text(bundle.social_by_ticker, t, post)
            bundle.social_posts.append({"ticker": t, "text": post, "source": "forum_seed"})
        if t in MOCK_ANALYST:
            bundle.analyst_by_ticker[t] = MOCK_ANALYST[t]
    if bundle.social_by_ticker:
        bundle.sources_used.append("forum_seed")
    if bundle.analyst_by_ticker:
        bundle.sources_used.append("analyst_notes_seed")

    timeout = httpx.Timeout(8.0, connect=3.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Local news intelligence service
        try:
            data = await _fetch_json(client, f"{news_url.rstrip('/')}/v1/news?limit=40")
            if isinstance(data, list):
                bundle.sources_used.append("news_intelligence")
                for article in data:
                    title = str(article.get("title") or "")
                    body = str(article.get("body") or "")
                    source = str(article.get("source") or "news")
                    companies = article.get("companies") or []
                    text = f"{title}. {body}"
                    targets = [str(c).upper() for c in companies if str(c).upper() in universe]
                    if not targets:
                        targets = _detect_tickers(text, universe)
                    for t in targets or []:
                        _append_text(bundle.news_by_ticker, t, f"[{source}] {text}")
                    bundle.headlines.append(
                        {
                            "source": source,
                            "title": title,
                            "tickers": targets,
                            "sentiment": article.get("sentiment"),
                        }
                    )
        except Exception:
            logger.exception("intel_news_service_failed")

        # Local filings / announcements
        try:
            data = await _fetch_json(
                client, f"{announcements_url.rstrip('/')}/v1/announcements?limit=40"
            )
            if isinstance(data, list):
                bundle.sources_used.append("company_announcements")
                for filing in data:
                    t = str(filing.get("company_ticker") or "").upper()
                    if t not in universe:
                        continue
                    impact = float(filing.get("impact_score") or 0.0)
                    bundle.announcement_impact[t] = bundle.announcement_impact.get(t, 0.0) + impact
                    title = str(filing.get("title") or "")
                    summary = str(filing.get("summary") or "")
                    _append_text(
                        bundle.news_by_ticker,
                        t,
                        f"[filing:{filing.get('filing_type')}] {title}. {summary}",
                    )
        except Exception:
            logger.exception("intel_announcements_failed")

        if include_web:
            # Public RSS outlets
            for name, url in RSS_OUTLETS:
                items = await _fetch_rss(client, name, url)
                if not items:
                    continue
                if name not in bundle.sources_used:
                    bundle.sources_used.append(f"rss:{name}")
                for item in items:
                    text = f"{item['title']}. {item.get('body', '')}"
                    targets = _detect_tickers(text, universe)
                    for t in targets:
                        _append_text(bundle.news_by_ticker, t, f"[{name}] {text}")
                    bundle.headlines.append(
                        {
                            "source": name,
                            "title": item["title"],
                            "tickers": targets,
                        }
                    )

            # Reddit forums / social
            for label, url in REDDIT_FORUMS:
                payload = await _fetch_json(client, url)
                children = (
                    ((payload or {}).get("data") or {}).get("children")
                    if isinstance(payload, dict)
                    else None
                )
                if not children:
                    continue
                if label not in bundle.sources_used:
                    bundle.sources_used.append(label)
                for child in children[:12]:
                    data = (child or {}).get("data") or {}
                    title = str(data.get("title") or "")
                    body = str(data.get("selftext") or "")[:400]
                    text = f"{title}. {body}".strip()
                    targets = _detect_tickers(text, universe)
                    if not targets:
                        # Broad market chatter → SPY if in universe
                        if "SPY" in universe:
                            targets = ["SPY"]
                        else:
                            continue
                    for t in targets:
                        _append_text(bundle.social_by_ticker, t, f"[{label}] {text}")
                        bundle.social_posts.append(
                            {"ticker": t, "text": text[:240], "source": label}
                        )

    # In-process macro + geo (seeded engines — no paid keys)
    try:
        from macro.engine import MacroEngine

        macro = MacroEngine()
        indicators = macro.latest_indicators()
        bundle.sources_used.append("macro_engine")
        for ind in indicators[:8]:
            surprise = float(ind.surprise or 0.0)
            if abs(surprise) < 0.1:
                continue
            # Soft bias: hot inflation / strong labor → pressure high-beta names
            for t in universe:
                bias = -0.05 * surprise if t in {"SPY", "QQQ", "NVDA", "TSLA"} else -0.02 * surprise
                bundle.macro_bias[t] = bundle.macro_bias.get(t, 0.0) + bias
                _append_text(
                    bundle.analyst_by_ticker,
                    t,
                    f"[macro:{ind.name}] value={ind.value} surprise={surprise}",
                )
    except Exception:
        logger.debug("intel_macro_unavailable")

    try:
        from geopolitical.engine import GeopoliticalEngine

        geo = GeopoliticalEngine()
        events = geo.list_events(limit=10)
        bundle.sources_used.append("geopolitical_engine")
        for event in events:
            impacts = event.impacts or {}
            oil = float(impacts.get("oil") or 0.0)
            semis = float(impacts.get("semiconductors") or 0.0)
            for t in universe:
                delta = 0.0
                if t in {"XOM"} and oil:
                    delta += 0.08 * oil
                if t in {"NVDA", "AAPL", "MSFT"} and semis:
                    delta += 0.06 * semis
                if t in {"SPY", "QQQ"} and (oil or semis):
                    delta += 0.03 * (oil + semis) / 2
                if delta:
                    bundle.geo_bias[t] = bundle.geo_bias.get(t, 0.0) + delta
                    _append_text(
                        bundle.news_by_ticker,
                        t,
                        f"[geo:{event.event_type}] {event.title}. {event.summary}",
                    )
    except Exception:
        logger.debug("intel_geo_unavailable")

    logger.info(
        "intelligence_gathered",
        sources=bundle.sources_used,
        news_tickers=len(bundle.news_by_ticker),
        social_tickers=len(bundle.social_by_ticker),
        headlines=len(bundle.headlines),
    )
    return bundle
