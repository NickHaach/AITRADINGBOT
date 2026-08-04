"""Rule + lexicon based news classifier (deterministic, offline-capable).

Production deployments can swap in an LLM or HuggingFace classifier behind
ClassifierPort; this implementation is fully testable without network.
"""

from __future__ import annotations

import re

from ai_trading_shared.domain.enums import NewsCategory, RiskLevel, SentimentLabel, Urgency

# ticker-like tokens
_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")

CATEGORY_KEYWORDS: dict[NewsCategory, tuple[str, ...]] = {
    NewsCategory.CENTRAL_BANK: ("federal reserve", "ecb", "boe", "rba", "interest rate", "fomc"),
    NewsCategory.GEOPOLITICAL: ("war", "sanctions", "missile", "invasion", "conflict", "tariff"),
    NewsCategory.ENERGY: ("oil", "opec", "natural gas", "crude", "refinery", "lng"),
    NewsCategory.TECHNOLOGY: ("semiconductor", "ai ", "chip", "software", "cloud", "nvidia"),
    NewsCategory.DEFENSE: ("defense", "military", "pentagon", "arms", "nato"),
    NewsCategory.HEALTHCARE: ("fda", "drug", "pharma", "clinical trial", "biotech"),
    NewsCategory.CRYPTO: ("bitcoin", "ethereum", "crypto", "blockchain", "stablecoin"),
    NewsCategory.GOVERNMENT: ("congress", "parliament", "regulation", "antitrust", "sec filing"),
    NewsCategory.FINANCIAL: ("earnings", "revenue", "ipo", "merger", "dividend", "bank"),
    NewsCategory.BREAKING: ("breaking", "urgent", "just in"),
}

SECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Energy": ("oil", "gas", "opec", "crude"),
    "Technology": ("software", "chip", "semiconductor", "ai", "cloud"),
    "Financials": ("bank", "lending", "credit", "fintech"),
    "Healthcare": ("pharma", "biotech", "hospital", "drug"),
    "Defense": ("defense", "military", "aerospace"),
    "Consumer": ("retail", "consumer", "e-commerce"),
    "Industrials": ("manufacturing", "shipping", "logistics"),
    "Crypto": ("bitcoin", "crypto", "ethereum"),
}

COUNTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "US": ("united states", " washington", "wall street", "federal reserve", "u.s."),
    "CN": ("china", "beijing", "pboc", "yuan"),
    "EU": ("european union", "eurozone", "brussels", "ecb"),
    "UK": ("britain", "uk ", "london", "boe", "sterling"),
    "JP": ("japan", "tokyo", "boj", "yen"),
    "AU": ("australia", "asx", "rba"),
    "RU": ("russia", "moscow", "kremlin"),
    "UA": ("ukraine", "kyiv", "kiev"),
    "IL": ("israel", "tel aviv"),
    "SA": ("saudi", "aramco"),
}

BULLISH = (
    "beat", "surge", "rally", "record high", "upgrade", "growth", "strong demand",
    "profit", "expansion", "breakthrough",
)
BEARISH = (
    "miss", "plunge", "crash", "downgrade", "recession", "layoff", "default",
    "sanction", "war", "shortage", "bankruptcy", "fraud",
)
HIGH_RISK = ("war", "default", "crash", "sanction", "nuclear", "bankruptcy", "fraud")
BREAKING = ("breaking", "just in", "urgent", "alert")

KNOWN_COMPANIES: dict[str, str] = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "meta": "META",
    "exxon": "XOM",
    "chevron": "CVX",
    "jpmorgan": "JPM",
    "goldman": "GS",
    "lockheed": "LMT",
    "raytheon": "RTX",
    "pfizer": "PFE",
}


class LexiconNewsClassifier:
    """Deterministic classifier implementing ClassifierPort."""

    async def classify(self, title: str, body: str) -> dict:
        text = f"{title}\n{body}".lower()
        category = self._category(text)
        sectors = self._match_map(text, SECTOR_KEYWORDS)
        countries = self._match_map(text, COUNTRY_KEYWORDS)
        companies = self._companies(text, title)
        sentiment_score, sentiment = self._sentiment(text)
        risk = self._risk(text, sentiment_score)
        urgency = self._urgency(text, category)
        confidence = self._confidence(sectors, countries, companies, category)

        return {
            "category": category,
            "sectors": sectors,
            "countries": countries,
            "companies": companies,
            "industries": sectors[:],  # coarse proxy; NER model can refine later
            "risk_level": risk,
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "confidence": confidence,
            "urgency": urgency,
        }

    def _category(self, text: str) -> NewsCategory:
        best = NewsCategory.OTHER
        best_hits = 0
        for cat, kws in CATEGORY_KEYWORDS.items():
            hits = sum(1 for kw in kws if kw in text)
            if hits > best_hits:
                best_hits = hits
                best = cat
        return best

    def _match_map(self, text: str, mapping: dict[str, tuple[str, ...]]) -> list[str]:
        found: list[str] = []
        for key, kws in mapping.items():
            if any(kw in text for kw in kws):
                found.append(key)
        return found

    def _companies(self, text: str, title: str) -> list[str]:
        found: list[str] = []
        for name, ticker in KNOWN_COMPANIES.items():
            if name in text:
                found.append(ticker)
        # uppercase tickers in title (avoid common short words)
        skip = {"US", "EU", "UK", "CEO", "IPO", "ETF", "AI", "GDP", "FED", "SEC", "THE", "AND", "FOR"}
        for match in _TICKER_RE.findall(title):
            if match not in skip and match not in found:
                found.append(match)
        return found[:20]

    def _sentiment(self, text: str) -> tuple[float, SentimentLabel]:
        bull = sum(1 for w in BULLISH if w in text)
        bear = sum(1 for w in BEARISH if w in text)
        total = bull + bear
        if total == 0:
            return 0.0, SentimentLabel.NEUTRAL
        score = (bull - bear) / total
        if score <= -0.6:
            label = SentimentLabel.VERY_BEARISH
        elif score <= -0.2:
            label = SentimentLabel.BEARISH
        elif score >= 0.6:
            label = SentimentLabel.VERY_BULLISH
        elif score >= 0.2:
            label = SentimentLabel.BULLISH
        else:
            label = SentimentLabel.NEUTRAL
        return round(score, 4), label

    def _risk(self, text: str, sentiment_score: float) -> RiskLevel:
        if any(w in text for w in HIGH_RISK):
            return RiskLevel.CRITICAL if "nuclear" in text or "default" in text else RiskLevel.HIGH
        if sentiment_score <= -0.5:
            return RiskLevel.HIGH
        if abs(sentiment_score) >= 0.3:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _urgency(self, text: str, category: NewsCategory) -> Urgency:
        if any(w in text for w in BREAKING) or category == NewsCategory.BREAKING:
            return Urgency.BREAKING
        if category in {NewsCategory.GEOPOLITICAL, NewsCategory.CENTRAL_BANK}:
            return Urgency.HIGH
        if category in {NewsCategory.FINANCIAL, NewsCategory.ENERGY}:
            return Urgency.MEDIUM
        return Urgency.LOW

    def _confidence(
        self,
        sectors: list[str],
        countries: list[str],
        companies: list[str],
        category: NewsCategory,
    ) -> float:
        score = 0.4
        if category != NewsCategory.OTHER:
            score += 0.2
        if sectors:
            score += 0.15
        if countries:
            score += 0.1
        if companies:
            score += 0.15
        return round(min(score, 0.95), 4)
