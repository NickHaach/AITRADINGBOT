"""Geopolitical engine tests."""

from __future__ import annotations

from ai_trading_shared.domain.enums import RiskLevel
from geopolitical.engine import GeopoliticalEngine


def test_seed_events_and_assess() -> None:
    engine = GeopoliticalEngine()
    assert len(engine.list_events()) >= 3
    event = engine.assess(
        title="Naval blockade risk in Strait of Hormuz",
        event_type="shipping",
        countries=["IR", "SA"],
        severity=RiskLevel.CRITICAL,
    )
    assert event.impacts["oil"] > 0
    assert event.impacts["shipping"] > 0
    assert event.confidence >= 0.5
