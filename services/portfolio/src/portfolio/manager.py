"""Portfolio Manager — tracks cash, equity, exposure, and performance."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ai_trading_shared.domain.entities import PortfolioSnapshot, Position, Trade
from ai_trading_shared.domain.enums import Side


class PortfolioManager:
    def __init__(self, starting_cash: Decimal = Decimal("100000")) -> None:
        self.cash = starting_cash
        self.positions: dict[str, Position] = {}
        self.realized_pnl = Decimal("0")
        self.peak_equity = starting_cash
        self._history: list[PortfolioSnapshot] = []

    def apply_trade(self, trade: Trade, sector: str | None = None, country: str | None = None) -> None:
        notional = trade.quantity * trade.price
        if trade.side == Side.BUY:
            self.cash -= notional + trade.fees
            existing = self.positions.get(trade.ticker)
            if existing is None:
                self.positions[trade.ticker] = Position(
                    ticker=trade.ticker,
                    quantity=trade.quantity,
                    avg_cost=trade.price,
                    market_value=notional,
                    unrealized_pnl=Decimal("0"),
                    sector=sector,
                    country=country,
                )
            else:
                new_qty = existing.quantity + trade.quantity
                new_cost = (
                    (existing.avg_cost * existing.quantity) + (trade.price * trade.quantity)
                ) / new_qty
                self.positions[trade.ticker] = existing.model_copy(
                    update={
                        "quantity": new_qty,
                        "avg_cost": new_cost,
                        "market_value": new_qty * trade.price,
                    }
                )
        else:
            existing = self.positions.get(trade.ticker)
            if existing is None:
                raise ValueError(f"Cannot sell {trade.ticker}: no position")
            pnl = (trade.price - existing.avg_cost) * trade.quantity - trade.fees
            self.realized_pnl += pnl
            self.cash += notional - trade.fees
            remaining = existing.quantity - trade.quantity
            if remaining <= 0:
                del self.positions[trade.ticker]
            else:
                self.positions[trade.ticker] = existing.model_copy(
                    update={
                        "quantity": remaining,
                        "market_value": remaining * trade.price,
                        "unrealized_pnl": (trade.price - existing.avg_cost) * remaining,
                    }
                )

    def mark_to_market(self, prices: dict[str, Decimal]) -> PortfolioSnapshot:
        positions: list[Position] = []
        market_value = Decimal("0")
        for ticker, pos in self.positions.items():
            px = prices.get(ticker, pos.avg_cost)
            mv = pos.quantity * px
            upnl = (px - pos.avg_cost) * pos.quantity
            market_value += mv
            positions.append(
                pos.model_copy(update={"market_value": mv, "unrealized_pnl": upnl})
            )
            self.positions[ticker] = positions[-1]

        equity = self.cash + market_value
        self.peak_equity = max(self.peak_equity, equity)
        drawdown = float((self.peak_equity - equity) / self.peak_equity) if self.peak_equity else 0.0
        snap = PortfolioSnapshot(
            cash=self.cash,
            equity=equity,
            positions=positions,
            total_pnl=self.realized_pnl + sum((p.unrealized_pnl for p in positions), Decimal("0")),
            drawdown_pct=drawdown,
            as_of=datetime.utcnow(),
        )
        self._history.append(snap)
        return snap

    @property
    def history(self) -> list[PortfolioSnapshot]:
        return list(self._history)
