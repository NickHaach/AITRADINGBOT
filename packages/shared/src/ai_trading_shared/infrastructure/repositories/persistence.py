"""Persistence repositories for market features, predictions, and outcomes.

Uses SQLAlchemy async sessions. For local tests, point at sqlite+aiosqlite.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_shared.domain.entities import Prediction
from ai_trading_shared.infrastructure.db_models import (
    MarketBarRow,
    MarketFeatureRow,
    PortfolioSnapshotRow,
    PredictionRow,
    TradeOutcomeRow,
)


class MarketPersistenceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def upsert_bars(self, bars: List[Dict[str, Any]]) -> int:
        if not bars:
            return 0
        async with self._factory() as session:
            count = 0
            for bar in bars:
                existing = await session.scalar(
                    select(MarketBarRow).where(
                        MarketBarRow.ticker == bar["ticker"],
                        MarketBarRow.timestamp == bar["timestamp"],
                    )
                )
                if existing is None:
                    session.add(
                        MarketBarRow(
                            ticker=bar["ticker"],
                            asset_class=bar.get("asset_class", "stock"),
                            timestamp=bar["timestamp"],
                            open=Decimal(str(bar["open"])),
                            high=Decimal(str(bar["high"])),
                            low=Decimal(str(bar["low"])),
                            close=Decimal(str(bar["close"])),
                            volume=Decimal(str(bar.get("volume", 0))),
                            vwap=Decimal(str(bar["vwap"])) if bar.get("vwap") is not None else None,
                        )
                    )
                    count += 1
                else:
                    existing.open = Decimal(str(bar["open"]))
                    existing.high = Decimal(str(bar["high"]))
                    existing.low = Decimal(str(bar["low"]))
                    existing.close = Decimal(str(bar["close"]))
                    existing.volume = Decimal(str(bar.get("volume", 0)))
                    count += 1
            await session.commit()
            return count

    async def save_features(self, features: Dict[str, Any]) -> Dict[str, Any]:
        async with self._factory() as session:
            row = await session.scalar(
                select(MarketFeatureRow).where(MarketFeatureRow.ticker == features["ticker"])
            )
            if row is None:
                row = MarketFeatureRow(ticker=features["ticker"])
                session.add(row)
            for key in (
                "as_of",
                "last_price",
                "returns_1d",
                "returns_5d",
                "returns_20d",
                "volatility_10d",
                "volatility_20d",
                "volume_zscore_20d",
                "liquidity_score",
                "trend_strength",
                "high_20d",
                "low_20d",
                "distance_from_high_20d",
                "bars_used",
            ):
                setattr(row, key, features[key])
            row.payload = features.get("payload", {})
            await session.commit()
            await session.refresh(row)
            return {"ticker": row.ticker, "last_price": float(row.last_price), "as_of": row.as_of}

    async def get_features(self, ticker: str) -> Optional[Dict[str, Any]]:
        async with self._factory() as session:
            row = await session.scalar(
                select(MarketFeatureRow).where(MarketFeatureRow.ticker == ticker.upper())
            )
            if row is None:
                return None
            return {
                "ticker": row.ticker,
                "as_of": row.as_of,
                "last_price": float(row.last_price),
                "returns_5d": float(row.returns_5d),
                "volatility_20d": float(row.volatility_20d),
                "liquidity_score": float(row.liquidity_score),
                "trend_strength": float(row.trend_strength),
                "bars_used": row.bars_used,
            }

    async def list_bar_tickers(self) -> List[str]:
        async with self._factory() as session:
            rows = (await session.scalars(select(MarketBarRow.ticker).distinct())).all()
            return sorted(set(rows))


class PredictionPersistenceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def save(self, prediction: Prediction) -> Prediction:
        async with self._factory() as session:
            session.add(
                PredictionRow(
                    id=prediction.id,
                    ticker=prediction.ticker,
                    model_name=prediction.model_name,
                    direction_prob_up=prediction.direction_prob_up,
                    expected_return=prediction.expected_return,
                    volatility_forecast=prediction.volatility_forecast,
                    trend_probability=prediction.trend_probability,
                    mean_reversion_probability=prediction.mean_reversion_probability,
                    breakout_probability=prediction.breakout_probability,
                    risk_score=prediction.risk_score,
                    horizon_days=prediction.horizon_days,
                    features=prediction.features,
                )
            )
            await session.commit()
            return prediction

    async def list_recent(self, ticker: Optional[str] = None, limit: int = 50) -> List[Prediction]:
        async with self._factory() as session:
            stmt = select(PredictionRow).order_by(PredictionRow.created_at.desc()).limit(limit)
            if ticker:
                stmt = stmt.where(PredictionRow.ticker == ticker.upper())
            rows = (await session.scalars(stmt)).all()
            return [
                Prediction(
                    id=r.id,
                    ticker=r.ticker,
                    model_name=r.model_name,
                    direction_prob_up=float(r.direction_prob_up),
                    expected_return=float(r.expected_return),
                    volatility_forecast=float(r.volatility_forecast),
                    trend_probability=float(r.trend_probability),
                    mean_reversion_probability=float(r.mean_reversion_probability),
                    breakout_probability=float(r.breakout_probability),
                    risk_score=float(r.risk_score),
                    horizon_days=r.horizon_days,
                    features=r.features or {},
                    created_at=r.created_at,
                )
                for r in rows
            ]


class OutcomePersistenceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def save(self, outcome: Dict[str, Any]) -> Dict[str, Any]:
        async with self._factory() as session:
            row = TradeOutcomeRow(
                id=outcome.get("id"),
                signal_id=outcome["signal_id"],
                trade_id=outcome.get("trade_id"),
                ticker=outcome["ticker"],
                action=outcome["action"],
                predicted_direction=outcome["predicted_direction"],
                predicted_return=outcome["predicted_return"],
                probability_success=outcome["probability_success"],
                confidence=outcome["confidence"],
                model_versions=outcome.get("model_versions", []),
                actual_return=outcome["actual_return"],
                holding_days=outcome["holding_days"],
                correct_direction=outcome["correct_direction"],
                pnl=outcome["pnl"],
                closed_at=outcome.get("closed_at") or datetime.utcnow(),
                notes=outcome.get("notes", ""),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return {"id": str(row.id), "ticker": row.ticker, "correct": row.correct_direction}

    async def list_recent(self, ticker: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        async with self._factory() as session:
            stmt = select(TradeOutcomeRow).order_by(TradeOutcomeRow.closed_at.desc()).limit(limit)
            if ticker:
                stmt = stmt.where(TradeOutcomeRow.ticker == ticker.upper())
            rows = (await session.scalars(stmt)).all()
            return [
                {
                    "id": str(r.id),
                    "ticker": r.ticker,
                    "correct_direction": r.correct_direction,
                    "predicted_return": float(r.predicted_return),
                    "actual_return": float(r.actual_return),
                    "confidence": float(r.confidence),
                }
                for r in rows
            ]

    async def list_for_eval(self, limit: int = 5000) -> List[Dict[str, Any]]:
        """Full outcome rows for LearningEngine hydration / Celery eval windows."""
        async with self._factory() as session:
            stmt = select(TradeOutcomeRow).order_by(TradeOutcomeRow.closed_at.desc()).limit(limit)
            rows = (await session.scalars(stmt)).all()
            return [
                {
                    "id": r.id,
                    "signal_id": r.signal_id,
                    "trade_id": r.trade_id,
                    "ticker": r.ticker,
                    "action": r.action,
                    "predicted_direction": r.predicted_direction,
                    "predicted_return": float(r.predicted_return),
                    "probability_success": float(r.probability_success),
                    "confidence": float(r.confidence),
                    "model_versions": list(r.model_versions or []),
                    "actual_return": float(r.actual_return),
                    "holding_days": r.holding_days,
                    "correct_direction": r.correct_direction,
                    "pnl": float(r.pnl),
                    "closed_at": r.closed_at,
                    "notes": r.notes or "",
                }
                for r in rows
            ]

class PortfolioPersistenceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def save(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        async with self._factory() as session:
            row = PortfolioSnapshotRow(
                id=snapshot.get("id"),
                cash=Decimal(str(snapshot["cash"])),
                equity=Decimal(str(snapshot["equity"])),
                positions=snapshot.get("positions") or [],
                total_pnl=Decimal(str(snapshot["total_pnl"])),
                drawdown_pct=float(snapshot["drawdown_pct"]),
                as_of=snapshot.get("as_of") or datetime.utcnow(),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return {
                "id": str(row.id),
                "equity": float(row.equity),
                "cash": float(row.cash),
                "drawdown_pct": float(row.drawdown_pct),
                "as_of": row.as_of.isoformat() if row.as_of else None,
            }

    async def latest(self) -> Optional[Dict[str, Any]]:
        async with self._factory() as session:
            row = await session.scalar(
                select(PortfolioSnapshotRow).order_by(PortfolioSnapshotRow.as_of.desc()).limit(1)
            )
            if row is None:
                return None
            return _portfolio_row(row)

    async def list_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        async with self._factory() as session:
            rows = (
                await session.scalars(
                    select(PortfolioSnapshotRow)
                    .order_by(PortfolioSnapshotRow.as_of.desc())
                    .limit(limit)
                )
            ).all()
            return [_portfolio_row(r) for r in rows]


def _portfolio_row(row: PortfolioSnapshotRow) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "cash": float(row.cash),
        "equity": float(row.equity),
        "positions": row.positions or [],
        "total_pnl": float(row.total_pnl),
        "drawdown_pct": float(row.drawdown_pct),
        "as_of": row.as_of.isoformat() if row.as_of else None,
    }
