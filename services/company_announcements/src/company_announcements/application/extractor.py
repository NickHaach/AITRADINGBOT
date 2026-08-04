"""Deterministic filing extractor / impact scorer (offline-capable)."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import List, Tuple

from ai_trading_shared.domain.entities import Announcement
from ai_trading_shared.domain.enums import new_id
from company_announcements.domain.ports import RawFiling

_REVENUE = re.compile(
    r"(?:revenue|sales)\s+(?:of\s+)?\$?\s*([\d,.]+)\s*(billion|million|bn|m)?",
    re.I,
)
_EPS = re.compile(r"(?:EPS|earnings per share)\s+(?:of\s+)?\$?\s*([-\d,.]+)", re.I)
_MARGIN = re.compile(r"(?:operating |gross |net )?margin[s]?\s+(?:of\s+)?([\d.]+)\s*%", re.I)

BULLISH_CUES = (
    "beat",
    "raised guidance",
    "raises guidance",
    "above expectations",
    "record",
    "buyback",
    "share repurchase",
    "dividend increase",
    "strong demand",
)
BEARISH_CUES = (
    "miss",
    "cut guidance",
    "cuts guidance",
    "below expectations",
    "restructuring",
    "impairment",
    "investigation",
    "downgrade",
    "weak demand",
)
RISK_CUES = (
    "risk",
    "uncertainty",
    "litigation",
    "regulatory",
    "cyber",
    "supply chain",
    "inflation",
)
OPPORTUNITY_CUES = (
    "expansion",
    "launch",
    "acquisition",
    "partnership",
    "AI",
    "pipeline",
    "market share",
)


class LexiconAnnouncementExtractor:
    """Rule-based extractor implementing AnnouncementExtractorPort."""

    async def extract(self, filing: RawFiling) -> Announcement:
        text = f"{filing.title}\n{filing.body}"
        revenue = _parse_money(_REVENUE.search(text))
        eps = _parse_decimal(_EPS.search(text))
        margins = _parse_pct(_MARGIN.search(text))
        risks = _collect(text, RISK_CUES)
        opportunities = _collect(text, OPPORTUNITY_CUES)
        impact, summary = _score_impact(text, filing.filing_type)
        guidance = _extract_guidance(text)

        return Announcement(
            id=new_id(),
            company_ticker=filing.company_ticker.upper(),
            filing_type=filing.filing_type,
            title=filing.title,
            body=filing.body,
            source=filing.source,
            filed_at=filing.filed_at,
            revenue=revenue,
            eps=eps,
            margins=margins,
            forward_guidance=guidance,
            risks=risks,
            opportunities=opportunities,
            impact_score=impact,
            summary=summary,
        )


def _parse_money(match: re.Match | None) -> Decimal | None:
    if not match:
        return None
    try:
        value = Decimal(match.group(1).replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None
    unit = (match.group(2) or "").lower()
    if unit in {"billion", "bn"}:
        value *= Decimal("1000000000")
    elif unit in {"million", "m"}:
        value *= Decimal("1000000")
    return value


def _parse_decimal(match: re.Match | None) -> Decimal | None:
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


def _parse_pct(match: re.Match | None) -> Decimal | None:
    if not match:
        return None
    try:
        return Decimal(match.group(1)) / Decimal("100")
    except (InvalidOperation, AttributeError):
        return None


def _collect(text: str, cues: Tuple[str, ...]) -> List[str]:
    lower = text.lower()
    return [c for c in cues if c.lower() in lower][:8]


def _extract_guidance(text: str) -> str | None:
    lower = text.lower()
    for phrase in ("raised guidance", "raises guidance", "cut guidance", "cuts guidance", "reaffirmed guidance"):
        if phrase in lower:
            idx = lower.index(phrase)
            return text[idx : idx + 160].strip()
    return None


def _score_impact(text: str, filing_type: str) -> Tuple[float, str]:
    lower = text.lower()
    bull = sum(1 for c in BULLISH_CUES if c in lower)
    bear = sum(1 for c in BEARISH_CUES if c in lower)
    total = bull + bear
    raw = ((bull - bear) / total) if total else 0.0

    # material filing types amplify magnitude
    weight = {
        "8-K": 1.0,
        "10-K": 0.7,
        "10-Q": 0.8,
        "earnings": 1.0,
        "M&A": 1.1,
        "guidance": 1.0,
        "buyback": 0.6,
        "dividend": 0.4,
        "ASX": 0.9,
    }.get(filing_type, 0.8)
    score = max(-1.0, min(1.0, raw * weight))

    if score >= 0.35:
        summary = f"Constructive {filing_type} with bullish language dominance."
    elif score <= -0.35:
        summary = f"Adverse {filing_type} with bearish language dominance."
    else:
        summary = f"Mixed/neutral {filing_type}; limited directional signal."
    return round(score, 4), summary
