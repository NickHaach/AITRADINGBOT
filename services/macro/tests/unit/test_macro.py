"""Macro engine tests."""

from __future__ import annotations

from macro.engine import MacroEngine


def test_macro_indicators_seeded() -> None:
    engine = MacroEngine()
    indicators = engine.list_indicators(country="US")
    assert len(indicators) >= 4
    cpi = next(i for i in indicators if "CPI" in i.name)
    reaction = engine.estimate_reaction(cpi)
    assert "TLT" in reaction.expected_asset_moves or "SPY" in reaction.expected_asset_moves
    assert 0 < reaction.confidence <= 1


def test_calendar_upcoming() -> None:
    engine = MacroEngine()
    events = engine.list_calendar(days=30)
    assert len(events) >= 2
    assert all(e.importance in {"low", "medium", "high"} for e in events)
