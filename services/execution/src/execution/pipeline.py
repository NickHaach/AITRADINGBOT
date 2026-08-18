"""Trading pipeline: signal → risk → execution → portfolio.

Orchestrates market features + sentiment + announcements into a trade decision
loop with hard risk gating and paper execution. Closes matured paper lots into
Learning Engine outcomes and refreshes probability temperature when possible.
"""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol
from uuid import uuid4

from ai_trading_shared.domain.entities import Prediction, Signal, Trade
from ai_trading_shared.domain.enums import AssetClass, OrderStatus, SignalAction
from ai_trading_shared.utils.logging import get_logger
from execution.brokers.alpaca import build_broker_from_settings
from execution.outcomes import OutcomeLedger
from execution.service import ExecutionService, PaperBroker
from learning.calibration import last_fit, refresh_calibrator
from learning.infrastructure.dual_write import DualWriteLearningStore
from market_data.application.service import MarketDataService
from market_data.infrastructure.adapters.mock_provider import MockMarketDataProvider
from market_data.infrastructure.repositories.memory import InMemoryMarketRepository
from portfolio.manager import PortfolioManager
from prediction.ensemble import HeuristicEnsemble, TemperatureCalibrator
from prediction.infrastructure.dual_write import DualWritePredictionStore
from risk.engine import ProposedTrade, RiskConfig, RiskEngine
from sentiment.engine import SentimentEngine

logger = get_logger(__name__)


class PortfolioSnapshotWriter(Protocol):
    async def save(self, snapshot: Dict) -> Dict: ...


class TradingPipeline:
    """End-to-end trading loop: signal → risk → broker → portfolio."""

    def __init__(
        self,
        *,
        starting_cash: Decimal = Decimal("100000"),
        risk_config: Optional[RiskConfig] = None,
        prediction_store: Optional[DualWritePredictionStore] = None,
        portfolio_writer: Optional[PortfolioSnapshotWriter] = None,
        learning_store: Optional[DualWriteLearningStore] = None,
        paper_days_per_cycle: int = 1,
        calibrator: Optional[TemperatureCalibrator] = None,
        predictor=None,
        settings=None,
        broker=None,
    ) -> None:
        fit = last_fit()
        self.calibrator = calibrator or TemperatureCalibrator(
            temperature=float(fit.get("temperature") or 1.2)
        )
        self.market = MarketDataService(
            provider=MockMarketDataProvider(),
            repository=InMemoryMarketRepository(),
        )
        self.sentiment = SentimentEngine()
        self.predictor = predictor or HeuristicEnsemble(calibrator=self.calibrator)
        if hasattr(self.predictor, "calibrator") and calibrator is None:
            # keep predictor calibrator aligned with shared last_fit temperature
            try:
                self.predictor.calibrator.temperature = self.calibrator.temperature
            except Exception:
                pass
        self.risk = RiskEngine(risk_config or RiskConfig())
        self.settings = settings
        if broker is not None:
            self.broker = broker
        elif settings is not None:
            self.broker = build_broker_from_settings(settings)
        else:
            self.broker = PaperBroker()
        # External brokers (Alpaca paper/live) need execution enabled;
        # real-money URLs remain dual-flag gated inside AlpacaBroker.
        external = getattr(self.broker, "name", "paper") != "paper"
        self.execution = ExecutionService(self.broker, live_enabled=external)
        self.portfolio = PortfolioManager(starting_cash)
        self.prediction_store = prediction_store or DualWritePredictionStore()
        self.portfolio_writer = portfolio_writer
        self.learning_store = learning_store or DualWriteLearningStore()
        self.outcome_ledger = OutcomeLedger(learning=self.learning_store)
        self.paper_days_per_cycle = max(1, paper_days_per_cycle)
        self.signals: List[Signal] = []
        self.rejected: List[Dict] = []
        self.fills: List[Dict] = []
        self.closed_outcomes: List[Dict] = []
        self.cycle_log: List[Dict] = []
        self.blotter: List[Dict] = []

    async def run_once(
        self,
        tickers: Optional[List[str]] = None,
        *,
        news_by_ticker: Optional[Dict[str, str]] = None,
        announcement_impact: Optional[Dict[str, float]] = None,
        social_by_ticker: Optional[Dict[str, str]] = None,
        analyst_by_ticker: Optional[Dict[str, str]] = None,
        macro_bias: Optional[Dict[str, float]] = None,
        geo_bias: Optional[Dict[str, float]] = None,
        intelligence_summary: Optional[Dict] = None,
    ) -> Dict:
        tickers = tickers or ["AAPL", "MSFT", "NVDA", "XOM", "JPM"]
        news_by_ticker = news_by_ticker or {}
        announcement_impact = dict(announcement_impact or {})
        social_by_ticker = social_by_ticker or {}
        analyst_by_ticker = analyst_by_ticker or {}
        macro_bias = macro_bias or {}
        geo_bias = geo_bias or {}

        cycle_id = str(uuid4())
        cycle_at = datetime.now(timezone.utc).isoformat()
        fill_mark = len(self.fills)
        reject_mark = len(self.rejected)
        closed_mark = len(self.closed_outcomes)

        # Fold macro/geo soft biases into announcement_impact channel used by the model
        for t in tickers:
            extra = float(macro_bias.get(t, 0.0)) + float(geo_bias.get(t, 0.0))
            if extra:
                announcement_impact[t] = float(announcement_impact.get(t, 0.0)) + extra

        self.outcome_ledger.advance_clock(self.paper_days_per_cycle)
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
                analyst_text=analyst_by_ticker.get(ticker, ""),
                social_text=social_by_ticker.get(ticker, ""),
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
            sources = []
            if news_by_ticker.get(ticker):
                sources.append("news")
            if social_by_ticker.get(ticker):
                sources.append("social_forums")
            if analyst_by_ticker.get(ticker):
                sources.append("analyst")
            if abs(announcement_impact.get(ticker, 0.0)) > 1e-9:
                sources.append("filings_macro_geo")
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
                        "announcement_impact": announcement_impact.get(ticker, 0.0),
                        "macro_bias": macro_bias.get(ticker, 0.0),
                        "geo_bias": geo_bias.get(ticker, 0.0),
                    },
                    "sources": sources,
                    "news_excerpt": (news_by_ticker.get(ticker) or "")[:280],
                    "social_excerpt": (social_by_ticker.get(ticker) or "")[:220],
                },
                model_versions=[
                    prediction.model_name,
                    "sentiment_v1",
                    "market_features_v1",
                    "intel_multichannel_v1",
                ],
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
            # Stamp configured broker name onto the order for audit
            order = order.model_copy(update={"broker": getattr(self.broker, "name", "paper")})
            # Only open BUY lots for paper learning — SELL without inventory crashes portfolio
            if action != SignalAction.BUY:
                rejected += 1
                self.rejected.append({"ticker": ticker, "reasons": ["paper_learning_buys_only"]})
                continue

            filled = await self.execution.execute(order, proposal.reference_price)
            if filled.status == OrderStatus.REJECTED:
                rejected += 1
                self.rejected.append(
                    {
                        "ticker": ticker,
                        "reasons": [filled.reject_reason or "broker_rejected"],
                    }
                )
                continue
            if filled.status != OrderStatus.FILLED or filled.average_fill_price is None:
                rejected += 1
                self.rejected.append(
                    {
                        "ticker": ticker,
                        "reasons": [f"broker_status_{filled.status.value}"],
                        "broker_order_id": filled.broker_order_id,
                    }
                )
                continue

            trade = self._trade_from_fill(filled)
            self.portfolio.apply_trade(trade)
            approved += 1
            self.fills.append(
                {
                    "ticker": ticker,
                    "side": filled.side.value,
                    "qty": str(filled.filled_quantity),
                    "price": str(filled.average_fill_price),
                    "signal_id": str(signal.id),
                    "broker": filled.broker,
                    "broker_order_id": filled.broker_order_id,
                    "at": cycle_at,
                    "cycle_id": cycle_id,
                }
            )
            direction_raw = float((prediction.features or {}).get("direction_raw", prediction.direction_prob_up))
            self.outcome_ledger.register_fill(
                signal_id=signal.id,
                trade_id=trade.id,
                ticker=ticker,
                action=action,
                predicted_return=prediction.expected_return,
                direction_prob_up=float(prediction.direction_prob_up),
                direction_raw=direction_raw,
                confidence=float(signal.confidence),
                model_versions=signal.model_versions,
                entry_price=trade.price,
                quantity=trade.quantity,
                horizon_days=signal.time_horizon_days,
                features=dict(prediction.features or {}),
            )
            logger.info(
                "trade_filled",
                ticker=ticker,
                side=filled.side.value,
                broker=filled.broker,
            )

        final_prices = {}
        for t in tickers:
            f = await self.market.get_features(t)
            if f:
                final_prices[t] = Decimal(str(round(f.last_price, 4)))

        closed = await self.outcome_ledger.close_matured(
            final_prices,
            apply_closing_trade=self.portfolio.apply_trade,
        )
        for outcome in closed:
            self.closed_outcomes.append(outcome.model_dump(mode="json"))

        # Refresh calibrator from in-memory learning store when enough closes exist
        calib = refresh_calibrator(
            self.learning_store.list_outcomes(limit=500),
            calibrator=self.calibrator,
            min_samples=30,
        )
        if calib.get("updated"):
            self.predictor.calibrator.temperature = float(calib["temperature"])

        final = self.portfolio.mark_to_market(final_prices)
        await self._persist_portfolio(final)

        new_fills = self.fills[fill_mark:]
        new_rejects = self.rejected[reject_mark:]
        # Stamp rejects from this cycle
        for item in new_rejects:
            item.setdefault("at", cycle_at)
            item.setdefault("cycle_id", cycle_id)
        new_closed = self.closed_outcomes[closed_mark:]

        for fill in new_fills:
            self.blotter.append({"type": "fill", **fill})
        for rej in new_rejects:
            self.blotter.append(
                {
                    "type": "reject",
                    "ticker": rej.get("ticker"),
                    "reasons": rej.get("reasons") or [],
                    "at": rej.get("at", cycle_at),
                    "cycle_id": cycle_id,
                }
            )
        for outcome in new_closed:
            self.blotter.append(
                {
                    "type": "close",
                    "ticker": outcome.get("ticker"),
                    "pnl": outcome.get("pnl"),
                    "actual_return": outcome.get("actual_return"),
                    "predicted_return": outcome.get("predicted_return"),
                    "correct_direction": outcome.get("correct_direction"),
                    "at": cycle_at,
                    "cycle_id": cycle_id,
                }
            )

        cycle_entry = {
            "id": cycle_id,
            "at": cycle_at,
            "approved_trades": approved,
            "rejected_trades": rejected,
            "closed_outcomes": len(new_closed),
            "equity": float(final.equity),
            "cash": float(final.cash),
            "signals": len(tickers),
            "fills": new_fills,
            "rejected": new_rejects,
            "intelligence": intelligence_summary or {},
            "calibration": calib,
        }
        self.cycle_log.append(cycle_entry)
        self.blotter.append(
            {
                "type": "cycle",
                "cycle_id": cycle_id,
                "at": cycle_at,
                "approved_trades": approved,
                "rejected_trades": rejected,
                "closed_outcomes": len(new_closed),
                "sources": (intelligence_summary or {}).get("sources_used") or [],
                "headline_count": (intelligence_summary or {}).get("headline_count"),
                "social_count": (intelligence_summary or {}).get("social_count"),
            }
        )
        # Cap memory
        if len(self.blotter) > 500:
            self.blotter = self.blotter[-500:]
        if len(self.cycle_log) > 100:
            self.cycle_log = self.cycle_log[-100:]

        return {
            "approved_trades": approved,
            "rejected_trades": rejected,
            "signals": len(self.signals),
            "equity": float(final.equity),
            "cash": float(final.cash),
            "positions": len(final.positions),
            "fills": self.fills,
            "rejected": self.rejected,
            "closed_outcomes": len(closed),
            "open_lots": len(self.outcome_ledger.open_lots),
            "calibration": calib,
            "intelligence": intelligence_summary or {},
            "cycle_id": cycle_id,
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
            "openLots": len(self.outcome_ledger.open_lots),
            "calibrationTemperature": self.calibrator.temperature,
        }

    def blotter_payloads(self, limit: int = 80) -> List[Dict]:
        return list(reversed(self.blotter[-limit:]))

    def cycle_history_payloads(self, limit: int = 20) -> List[Dict]:
        return list(reversed(self.cycle_log[-limit:]))

    def journal_payload(self, limit: int = 50) -> Dict:
        outcomes = self.learning_store.list_outcomes(limit=limit)
        signal_map = {str(s.id): s for s in self.signals}
        entries: List[Dict] = []
        hits = 0
        for outcome in outcomes:
            sig = signal_map.get(str(outcome.signal_id))
            rationale = (sig.rationale if sig else {}) or {}
            if outcome.correct_direction:
                hits += 1
            entries.append(
                {
                    "id": str(outcome.id),
                    "ticker": outcome.ticker,
                    "action": outcome.action.value if hasattr(outcome.action, "value") else str(outcome.action),
                    "predictedReturn": float(outcome.predicted_return),
                    "actualReturn": float(outcome.actual_return),
                    "correctDirection": bool(outcome.correct_direction),
                    "pnl": float(outcome.pnl),
                    "confidence": float(outcome.confidence),
                    "holdingDays": int(outcome.holding_days),
                    "closedAt": outcome.closed_at.isoformat()
                    if getattr(outcome, "closed_at", None)
                    else None,
                    "sources": rationale.get("sources") or [],
                    "newsExcerpt": rationale.get("news_excerpt") or "",
                    "socialExcerpt": rationale.get("social_excerpt") or "",
                    "thesis": (
                        f"{(rationale.get('news_excerpt') or rationale.get('social_excerpt') or '')}".strip()
                        or "Model + risk gates"
                    )[:280],
                    "modelVersions": list(outcome.model_versions or []),
                }
            )
        n = len(entries)
        calib = refresh_calibrator(outcomes, calibrator=self.calibrator, min_samples=10)
        return {
            "entries": entries,
            "stats": {
                "sampleSize": n,
                "directionAccuracy": (hits / n) if n else None,
                "avgPredictedReturn": (sum(e["predictedReturn"] for e in entries) / n) if n else None,
                "avgActualReturn": (sum(e["actualReturn"] for e in entries) / n) if n else None,
                "avgPnl": (sum(e["pnl"] for e in entries) / n) if n else None,
            },
            "calibration": {
                "temperature": float(self.calibrator.temperature),
                "updated": bool(calib.get("updated")),
                "sampleSize": calib.get("sample_size"),
            },
            "openLots": len(self.outcome_ledger.open_lots),
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
                    "why": f"{signal.action.value.upper()} from {', '.join(signal.model_versions[:2])}"
                    + (
                        f" · sources: {', '.join((signal.rationale or {}).get('sources') or [])}"
                        if (signal.rationale or {}).get("sources")
                        else ""
                    ),
                    "risks": risks or ["Monitor headline and liquidity risk"],
                    "sources": (signal.rationale or {}).get("sources") or [],
                    "newsExcerpt": (signal.rationale or {}).get("news_excerpt") or "",
                    "socialExcerpt": (signal.rationale or {}).get("social_excerpt") or "",
                }
            )
            if len(cards) >= limit:
                break
        return cards

    @staticmethod
    def _trade_from_fill(filled) -> Trade:
        from ai_trading_shared.domain.enums import new_id

        qty = filled.filled_quantity or filled.quantity
        return Trade(
            id=new_id(),
            order_id=filled.id,
            ticker=filled.ticker,
            side=filled.side,
            quantity=qty,
            price=filled.average_fill_price,
        )

    @staticmethod
    def _action_from_prediction(prob_up: float, expected_return: float) -> SignalAction:
        if prob_up >= 0.58 and expected_return > 0:
            return SignalAction.BUY
        if prob_up <= 0.42 and expected_return < 0:
            return SignalAction.SELL
        return SignalAction.HOLD
