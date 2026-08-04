"""Sentiment engine tests."""

from __future__ import annotations

from ai_trading_shared.domain.enums import SentimentLabel
from sentiment.engine import SentimentEngine, score_text


def test_score_text_bullish() -> None:
    assert score_text("Analyst upgrade after earnings beat and rally") > 0


def test_composite_sentiment() -> None:
    engine = SentimentEngine()
    snap = engine.score(
        "NVDA",
        news_text="NVIDIA surge on record AI demand",
        analyst_text="Street upgrade to overweight",
        social_text="bullish momentum",
        insider_net_buys=0.2,
        institutional_flow=0.4,
    )
    assert snap.composite > 0
    assert snap.label in {SentimentLabel.BULLISH, SentimentLabel.VERY_BULLISH}
    assert engine.get("NVDA") is not None
