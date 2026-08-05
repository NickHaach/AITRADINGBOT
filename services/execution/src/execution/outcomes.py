"""Open-lot ledger — close paper fills into Learning Engine outcomes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from ai_trading_shared.domain.enums import SignalAction, Side, new_id
from ai_trading_shared.domain.entities import Trade
from ai_trading_shared.utils.logging import get_logger
from learning.domain.models import TradeOutcome
from learning.infrastructure.dual_write import DualWriteLearningStore

logger = get_logger(__name__)


@dataclass
class OpenLot:
    signal_id: UUID
    trade_id: UUID
    ticker: str
    action: SignalAction
    predicted_return: float
    direction_prob_up: float
    direction_raw: float
    confidence: float
    model_versions: List[str]
    entry_price: Decimal
    quantity: Decimal
    open_sim_day: int
    horizon_days: int
    opened_at: datetime = field(default_factory=datetime.utcnow)


class OutcomeLedger:
    """Tracks filled opens and closes them after a simulated horizon."""

    def __init__(self, learning: Optional[DualWriteLearningStore] = None) -> None:
        self.learning = learning or DualWriteLearningStore()
        self.open_lots: List[OpenLot] = []
        self.closed: List[TradeOutcome] = []
        self.sim_day = 0

    def advance_clock(self, days: int = 1) -> None:
        self.sim_day += max(1, days)

    def register_fill(
        self,
        *,
        signal_id: UUID,
        trade_id: UUID,
        ticker: str,
        action: SignalAction,
        predicted_return: float,
        direction_prob_up: float,
        direction_raw: float,
        confidence: float,
        model_versions: Sequence[str],
        entry_price: Decimal,
        quantity: Decimal,
        horizon_days: int,
    ) -> OpenLot:
        lot = OpenLot(
            signal_id=signal_id,
            trade_id=trade_id,
            ticker=ticker.upper(),
            action=action,
            predicted_return=predicted_return,
            direction_prob_up=direction_prob_up,
            direction_raw=direction_raw,
            confidence=confidence,
            model_versions=list(model_versions),
            entry_price=entry_price,
            quantity=quantity,
            open_sim_day=self.sim_day,
            horizon_days=max(1, horizon_days),
        )
        self.open_lots.append(lot)
        return lot

    async def close_matured(
        self,
        prices: Dict[str, Decimal],
        *,
        apply_closing_trade=None,
    ) -> List[TradeOutcome]:
        """Close lots whose simulated age >= horizon_days.

        apply_closing_trade: optional callable(Trade) to update portfolio book.
        """
        still_open: List[OpenLot] = []
        closed: List[TradeOutcome] = []
        for lot in self.open_lots:
            age = self.sim_day - lot.open_sim_day
            if age < lot.horizon_days:
                still_open.append(lot)
                continue
            exit_px = prices.get(lot.ticker, lot.entry_price)
            if lot.entry_price == 0:
                still_open.append(lot)
                continue
            raw_ret = float((exit_px - lot.entry_price) / lot.entry_price)
            # BUY profits when price up; SELL (short-ish paper) profits when price down
            actual_return = raw_ret if lot.action == SignalAction.BUY else -raw_ret
            pnl = float(lot.quantity) * float(exit_px - lot.entry_price)
            if lot.action == SignalAction.SELL:
                pnl = -pnl

            if apply_closing_trade is not None:
                side = Side.SELL if lot.action == SignalAction.BUY else Side.BUY
                try:
                    apply_closing_trade(
                        Trade(
                            id=new_id(),
                            order_id=new_id(),
                            ticker=lot.ticker,
                            side=side,
                            quantity=lot.quantity,
                            price=exit_px,
                        )
                    )
                except Exception:
                    logger.exception("closing_trade_apply_failed", ticker=lot.ticker)

            outcome = await self.learning.record_closed_trade(
                signal_id=lot.signal_id,
                trade_id=lot.trade_id,
                ticker=lot.ticker,
                action=lot.action,
                predicted_return=lot.predicted_return,
                # Always P(up) so Learning Brier matches evaluate() contract
                probability_success=lot.direction_prob_up,
                confidence=lot.confidence,
                model_versions=lot.model_versions,
                actual_return=actual_return,
                holding_days=lot.horizon_days,
                pnl=pnl,
                notes=json.dumps(
                    {
                        "direction_raw": lot.direction_raw,
                        "exit_price": float(exit_px),
                        "entry_price": float(lot.entry_price),
                        "sim_day_closed": self.sim_day,
                    }
                ),
            )
            closed.append(outcome)
            self.closed.append(outcome)
            logger.info(
                "lot_closed",
                ticker=lot.ticker,
                actual_return=actual_return,
                holding_days=lot.horizon_days,
            )
        self.open_lots = still_open
        return closed
