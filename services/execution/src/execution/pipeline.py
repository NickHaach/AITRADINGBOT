"""Trading pipeline: signal → risk → execution → portfolio.

Orchestrates market features + sentiment + announcements into a trade decision
loop with hard risk gating and paper execution.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Protocol

from ai_trading_shared.domain.entities import Prediction, Signal
from ai_trading_shared.domain.enums import AssetClass, SignalAction
from ai_trading_shared.utils.logging import get_logger
from execution.service import ExecutionService, PaperBroker
from market_data.application.service import MarketDataService
from market_data.infrastructure.adapters.mock_provider import MockMarketDataProvider
from market_data.infrastructure.repositories.memory import InMemoryMarketRepository
from portfolio.manager import PortfolioManager
from prediction.ensemble import HeuristicEnsemble
from prediction.infrastructure.dual_write import DualWritePredictionStore
from risk.engine import ProposedTrade, RiskConfig, RiskEngine
from sentiment.engine import SentimentEngine

logger = get_logger(__name__)


class PortfolioSnapshotWriter(Protocol):
    async def save(self, snapshot: Dict) -> Dict: ...


class TradingPipeline:
    """End-to-end paper trading loop for a ticker universe."""

    def __init__(
        self,
        *,
        starting_cash: Decimal = Decimal("100000"),
        risk_config: Optional[RiskConfig] = None,
        prediction_store: Optional[DualWritePredictionStore] = None,
        portfolio_writer: Optional[PortfolioSnapshotWriter] = None,
    ) -> None:
        self.market = MarketDataService(
            provider=MockMarketDataProvider(),
            repository=InMemoryMarketRepository(),
        )
        self.sentiment = SentimentEngine()
        self.predictor = HeuristicEnsemble()
        self.risk = RiskEngine(risk_config or RiskConfig())
        self.broker = PaperBroker()
        self.execution = ExecutionService(self.broker, live_enabled=False)
        self.portfolio = PortfolioManager(starting_cash)
        self.prediction_store = prediction_store or DualWritePredictionStore()
        self.portfolio_writer = portfolio_writer
        self.signals: List[Signal] = []
        self.rejected: List[Dict] = []
        self.fills: List[Dict] = []

    async def run_once(
        self,
        tickers: Optional[List[str]] = None,
        *,
        news_by_ticker: Optional[Dict[str, str]] = None,
        announcement_impact: Optional[Dict[str, float]] = None,
    ) -> Dict:
        tickers = tickers or ["AAPL", "MSFT", "NVDA", "XOM", "JPM"]
        news_by_ticker = news_by_ticker or {}
        announcement_impact = announcement_impact or {}

        await self.market.refresh_universe(tickers)
        snap = self.portfolio.mark_to_market({})
        approved = 0
        rejected = 0

        for ticker in tickers:
            features = await self.market.get_features(ticker)
            if features is None:
                continue
            sent = self.sentiment.score(
                ticker,
                news_text=news_by_ticker.get(ticker, ""),
                analyst_text="",
                social_text="",
            )
            prediction = self.predictor.predict(
                ticker,
                returns_5d=features.returns_5d,
                volatility_20d=features.volatility_20d,
                sentiment_score=sent.composite,
                announcement_impact=announcement_impact.get(ticker, 0.0),
            )
            await self._persist_prediction(prediction)
            action = self._action_from_prediction(prediction.direction_prob_up, prediction.expected_return)
            signal = Signal(
                ticker=ticker,
                asset_class=AssetClass.STOCK,
                action=action,
                expected_return=prediction.expected_return,
                probability_success=prediction.direction_prob_up
                if action == SignalAction.BUY
                else 1 - prediction.direction_prob_up,
                risk_score=prediction.risk_score,
                confidence=min(0.95, 0.5 + abs(prediction.direction_prob_up - 0.5)),
                time_horizon_days=prediction.horizon_days,
                rationale={
                    "prediction": prediction.model_dump(mode="json"),
                    "sentiment": sent.model_dump(mode="json"),
                    "features": {
                        "returns_5d": features.returns_5d,
                        "volatility_20d": features.volatility_20d,
                        "liquidity_score": features.liquidity_score,
                    },
                },
                model_versions=[prediction.model_name, "sentiment_v1", "market_features_v1"],
            )
            self.signals.append(signal)

            if action == SignalAction.HOLD:
                continue

            # refresh MTM with last prices for risk checks
            prices = {}
            for t in tickers:
                f = await self.market.get_features(t)
                if f:
                    prices[t] = Decimal(str(round(f.last_price, 4)))
            snap = self.portfolio.mark_to_market(prices)

            proposal = ProposedTrade(
                signal=signal,
                reference_price=Decimal(str(round(features.last_price, 4))),
                sector=None,
                country="US",
                daily_pnl_pct=float(snap.total_pnl / snap.equity) if snap.equity else 0.0,
            )
            decision = self.risk.evaluate(proposal, snap)
            if not decision.approved:
                rejected += 1
                self.rejected.append(
                    {"ticker": ticker, "reasons": decision.reasons, "checks": decision.checks}
                )
                logger.info("trade_rejected", ticker=ticker, reasons=decision.reasons)
                continue

            order = self.risk.to_order(proposal, decision)
            if order is None:
                rejected += 1
                continue
            filled = await self.execution.execute(order, proposal.reference_price)
            trade = self.broker.trades[-1]
            self.portfolio.apply_trade(trade)
            approved += 1
            self.fills.append(
                {
                    "ticker": ticker,
                    "side": filled.side.value,
                    "qty": str(filled.filled_quantity),
                    "price": str(filled.average_fill_price),
                    "signal_id": str(signal.id),
                }
            )
            logger.info("trade_filled", ticker=ticker, side=filled.side.value)

        final_prices = {}
        for t in tickers:
            f = await self.market.get_features(t)
            if f:
                final_prices[t] = Decimal(str(round(f.last_price, 4)))
        final = self.portfolio.mark_to_market(final_prices)
        await self._persist_portfolio(final)
        return {
            "approved_trades": approved,
            "rejected_trades": rejected,
            "signals": len(self.signals),
            "equity": float(final.equity),
            "cash": float(final.cash),
            "positions": len(final.positions),
            "fills": self.fills,
            "rejected": self.rejected,
        }

    async def _persist_prediction(self, prediction: Prediction) -> None:
        try:
            await self.prediction_store.save(prediction)
        except Exception:
            logger.exception("prediction_persist_failed", ticker=prediction.ticker)

    async def _persist_portfolio(self, snapshot) -> None:
        if self.portfolio_writer is None:
            return
        try:
            payload = {
                "id": snapshot.id,
                "cash": snapshot.cash,
                "equity": snapshot.equity,
                "positions": [p.model_dump(mode="json") for p in snapshot.positions],
                "total_pnl": snapshot.total_pnl,
                "drawdown_pct": snapshot.drawdown_pct,
                "as_of": snapshot.as_of,
            }
            await self.portfolio_writer.save(payload)
        except Exception:
            logger.exception("portfolio_snapshot_persist_failed")

    def latest_snapshot_payload(self) -> Dict:
        history = self.portfolio.history
        if not history:
            empty = self.portfolio.mark_to_market({})
            history = [empty]
        snap = history[-1]
        equity = float(snap.equity) or 1.0
        positions = []
        for p in snap.positions:
            qty = float(p.quantity)
            mv = float(p.market_value)
            last = mv / qty if qty else float(p.avg_cost)
            positions.append(
                {
                    "ticker": p.ticker,
                    "qty": qty,
                    "avgCost": float(p.avg_cost),
                    "last": last,
                    "pnl": float(p.unrealized_pnl),
                    "weight": mv / equity if equity else 0.0,
                    "marketValue": mv,
                }
            )
        return {
            "cash": float(snap.cash),
            "equity": float(snap.equity),
            "drawdown": float(snap.drawdown_pct),
            "totalPnl": float(snap.total_pnl),
            "positions": positions,
            "asOf": snap.as_of.isoformat() if snap.as_of else None,
        }

    def recommendation_payloads(self, limit: int = 8) -> List[Dict]:
        """Map recent non-HOLD signals into dashboard recommendation cards."""
        cards: List[Dict] = []
        for signal in reversed(self.signals):
            if signal.action == SignalAction.HOLD:
                continue
            pred = (signal.rationale or {}).get("prediction") or {}
            risks = []
            if signal.risk_score >= 0.6:
                risks.append("Elevated model risk score")
            if float(pred.get("volatility_forecast") or 0) >= 0.35:
                risks.append("High realized vol regime")
            cards.append(
                {
                    "ticker": signal.ticker,
                    "action": signal.action.value.upper(),
                    "confidence": float(signal.confidence),
                    "expectedReturn": float(signal.expected_return),
                    "why": f"{signal.action.value.upper()} from {', '.join(signal.model_versions[:2])}",
                    "risks": risks or ["Monitor headline and liquidity risk"],
                }
            )
            if len(cards) >= limit:
                break
        return cards

    @staticmethod
    def _action_from_prediction(prob_up: float, expected_return: float) -> SignalAction:
        if prob_up >= 0.58 and expected_return > 0:
            return SignalAction.BUY
        if prob_up <= 0.42 and expected_return < 0:
            return SignalAction.SELL
        return SignalAction.HOLD
