"""Risk + execution integration tests."""

from decimal import Decimal

import pytest

from ai_trading_shared.domain.entities import PortfolioSnapshot, Position, Signal
from ai_trading_shared.domain.enums import AssetClass, SignalAction
from execution.service import ExecutionService, PaperBroker
from risk.engine import ProposedTrade, RiskConfig, RiskEngine


def _signal(**overrides) -> Signal:
    base = dict(
        ticker="NVDA",
        asset_class=AssetClass.STOCK,
        action=SignalAction.BUY,
        expected_return=0.04,
        probability_success=0.62,
        risk_score=0.35,
        confidence=0.7,
        time_horizon_days=5,
        rationale={"why": "AI demand"},
        model_versions=["lexicon-v1"],
    )
    base.update(overrides)
    return Signal(**base)


def _portfolio(equity: str = "100000") -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=Decimal(equity),
        equity=Decimal(equity),
        positions=[],
        total_pnl=Decimal("0"),
        drawdown_pct=0.0,
    )


def test_risk_approves_reasonable_trade() -> None:
    engine = RiskEngine(RiskConfig())
    decision = engine.evaluate(
        ProposedTrade(signal=_signal(), reference_price=Decimal("100"), sector="Technology", country="US"),
        _portfolio(),
    )
    assert decision.approved
    assert decision.sized_quantity is not None
    assert decision.stop_loss is not None


def test_risk_rejects_kill_switch() -> None:
    engine = RiskEngine(RiskConfig(kill_switch=True))
    decision = engine.evaluate(
        ProposedTrade(signal=_signal(), reference_price=Decimal("100")),
        _portfolio(),
    )
    assert not decision.approved
    assert "Kill switch" in decision.reasons[0]


def test_risk_rejects_low_confidence() -> None:
    engine = RiskEngine(RiskConfig())
    decision = engine.evaluate(
        ProposedTrade(signal=_signal(confidence=0.2), reference_price=Decimal("100")),
        _portfolio(),
    )
    assert not decision.approved


def test_risk_rejects_sector_overload() -> None:
    engine = RiskEngine(RiskConfig(max_sector_exposure_pct=0.10))
    portfolio = PortfolioSnapshot(
        cash=Decimal("10000"),
        equity=Decimal("100000"),
        positions=[
            Position(
                ticker="MSFT",
                quantity=Decimal("50"),
                avg_cost=Decimal("400"),
                market_value=Decimal("20000"),
                unrealized_pnl=Decimal("0"),
                sector="Technology",
                country="US",
            )
        ],
        total_pnl=Decimal("0"),
        drawdown_pct=0.0,
    )
    # 5% position = 5000, plus existing 20000 = 25% > 10%
    decision = engine.evaluate(
        ProposedTrade(
            signal=_signal(),
            reference_price=Decimal("100"),
            sector="Technology",
            country="US",
        ),
        portfolio,
    )
    assert not decision.approved
    assert any("Sector" in r for r in decision.reasons)


@pytest.mark.asyncio
async def test_paper_execution_fills() -> None:
    risk = RiskEngine(RiskConfig())
    proposal = ProposedTrade(signal=_signal(), reference_price=Decimal("100"))
    decision = risk.evaluate(proposal, _portfolio())
    order = risk.to_order(proposal, decision)
    assert order is not None
    exec_svc = ExecutionService(PaperBroker(), live_enabled=False)
    filled = await exec_svc.execute(order, Decimal("100.50"))
    assert filled.status.value == "filled"
    assert filled.average_fill_price == Decimal("100.50")
