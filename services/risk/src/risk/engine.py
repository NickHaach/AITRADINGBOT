"""Fix Order creation in RiskEngine — use OrderStatus enum."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from ai_trading_shared.domain.entities import Order, PortfolioSnapshot, RiskDecision, Signal
from ai_trading_shared.domain.enums import OrderStatus, OrderType, Side, SignalAction


class RiskConfig(BaseModel):
    max_position_pct: float = 0.05
    max_portfolio_risk_pct: float = 0.20
    daily_loss_limit_pct: float = 0.02
    max_sector_exposure_pct: float = 0.25
    max_country_exposure_pct: float = 0.40
    max_drawdown_pct: float = 0.15
    default_stop_loss_pct: float = 0.03
    default_take_profit_pct: float = 0.06
    kill_switch: bool = False


class ProposedTrade(BaseModel):
    signal: Signal
    reference_price: Decimal
    sector: str | None = None
    country: str | None = None
    daily_pnl_pct: float = 0.0


class RiskEngine:
    """Validates and sizes trades. Rejects violations — never soft-fails."""

    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    def evaluate(self, proposal: ProposedTrade, portfolio: PortfolioSnapshot) -> RiskDecision:
        reasons: list[str] = []
        checks: dict[str, bool] = {}

        if self.config.kill_switch:
            return RiskDecision(
                approved=False,
                reasons=["Kill switch engaged"],
                checks={"kill_switch": False},
            )

        checks["kill_switch"] = True

        if portfolio.drawdown_pct >= self.config.max_drawdown_pct:
            reasons.append(
                f"Max drawdown breached: {portfolio.drawdown_pct:.2%} >= {self.config.max_drawdown_pct:.2%}"
            )
            checks["max_drawdown"] = False
        else:
            checks["max_drawdown"] = True

        if proposal.daily_pnl_pct <= -self.config.daily_loss_limit_pct:
            reasons.append(f"Daily loss limit hit: {proposal.daily_pnl_pct:.2%}")
            checks["daily_loss"] = False
        else:
            checks["daily_loss"] = True

        if proposal.signal.action == SignalAction.HOLD:
            return RiskDecision(approved=False, reasons=["Signal action is HOLD"], checks=checks)

        if proposal.signal.confidence < 0.45:
            reasons.append(f"Confidence too low: {proposal.signal.confidence}")
            checks["confidence"] = False
        else:
            checks["confidence"] = True

        if proposal.signal.risk_score > 0.85:
            reasons.append(f"Risk score too high: {proposal.signal.risk_score}")
            checks["risk_score"] = False
        else:
            checks["risk_score"] = True

        equity = portfolio.equity if portfolio.equity > 0 else Decimal("1")
        max_notional = equity * Decimal(str(self.config.max_position_pct))
        sized_qty = (max_notional / proposal.reference_price).quantize(Decimal("0.000001"))
        if sized_qty <= 0:
            reasons.append("Sized quantity is zero")
            checks["sizing"] = False
        else:
            checks["sizing"] = True

        if proposal.sector:
            sector_value = sum(
                (p.market_value for p in portfolio.positions if p.sector == proposal.sector),
                Decimal("0"),
            )
            projected = sector_value + (sized_qty * proposal.reference_price)
            sector_pct = float(projected / equity)
            if sector_pct > self.config.max_sector_exposure_pct:
                reasons.append(f"Sector exposure {proposal.sector} would be {sector_pct:.2%}")
                checks["sector"] = False
            else:
                checks["sector"] = True
        else:
            checks["sector"] = True

        if proposal.country:
            country_value = sum(
                (p.market_value for p in portfolio.positions if p.country == proposal.country),
                Decimal("0"),
            )
            projected = country_value + (sized_qty * proposal.reference_price)
            country_pct = float(projected / equity)
            if country_pct > self.config.max_country_exposure_pct:
                reasons.append(f"Country exposure {proposal.country} would be {country_pct:.2%}")
                checks["country"] = False
            else:
                checks["country"] = True
        else:
            checks["country"] = True

        gross = sum((abs(p.market_value) for p in portfolio.positions), Decimal("0"))
        projected_gross = gross + (sized_qty * proposal.reference_price)
        gross_pct = float(projected_gross / equity)
        if gross_pct > self.config.max_portfolio_risk_pct:
            reasons.append(f"Portfolio risk {gross_pct:.2%} exceeds cap")
            checks["portfolio_risk"] = False
        else:
            checks["portfolio_risk"] = True

        approved = len(reasons) == 0
        stop = None
        take = None
        if approved:
            px = proposal.reference_price
            if proposal.signal.action in {SignalAction.BUY, SignalAction.HEDGE}:
                stop = px * (Decimal("1") - Decimal(str(self.config.default_stop_loss_pct)))
                take = px * (Decimal("1") + Decimal(str(self.config.default_take_profit_pct)))
            else:
                stop = px * (Decimal("1") + Decimal(str(self.config.default_stop_loss_pct)))
                take = px * (Decimal("1") - Decimal(str(self.config.default_take_profit_pct)))

        return RiskDecision(
            approved=approved,
            reasons=reasons,
            sized_quantity=sized_qty if approved else None,
            stop_loss=stop,
            take_profit=take,
            checks=checks,
        )

    def to_order(self, proposal: ProposedTrade, decision: RiskDecision) -> Order | None:
        if not decision.approved or decision.sized_quantity is None:
            return None
        side = (
            Side.BUY
            if proposal.signal.action in {SignalAction.BUY, SignalAction.HEDGE}
            else Side.SELL
        )
        return Order(
            signal_id=proposal.signal.id,
            ticker=proposal.signal.ticker,
            side=side,
            order_type=OrderType.MARKET,
            quantity=decision.sized_quantity,
            stop_price=decision.stop_loss,
            status=OrderStatus.PENDING,
            broker="paper",
        )
