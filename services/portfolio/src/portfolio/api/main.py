"""Portfolio desk FastAPI — live paper book + pipeline runner."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, List, Optional

from fastapi import Depends, FastAPI, Query

from ai_trading_shared.config import Settings, get_settings
from ai_trading_shared.infrastructure.database import create_engine, create_session_factory
from ai_trading_shared.infrastructure.repositories.model_registry import ModelRegistryRepository
from ai_trading_shared.infrastructure.repositories.persistence import (
    OutcomePersistenceRepository,
    PortfolioPersistenceRepository,
    PredictionPersistenceRepository,
)
from ai_trading_shared.utils.logging import configure_logging, get_logger
from execution.pipeline import TradingPipeline
from learning.infrastructure.dual_write import DualWriteLearningStore
from prediction.artifacts import load_gbm
from prediction.infrastructure.dual_write import DualWritePredictionStore

logger = get_logger(__name__)
_pipeline: Optional[TradingPipeline] = None


async def _resolve_predictor(settings: Settings):
    from learning.calibration import last_fit
    from prediction.ensemble import TemperatureCalibrator

    fit = last_fit()
    calibrator = TemperatureCalibrator(temperature=float(fit.get("temperature") or 1.2))
    if not (settings.enable_sql_persistence and settings.database_url.startswith("postgresql")):
        return None, calibrator
    try:
        engine = create_engine(settings.database_url)
        registry = ModelRegistryRepository(create_session_factory(engine))
        prod = await registry.get_production("gbm_direction_v1")
        await engine.dispose()
        if prod and prod.get("artifact_uri"):
            model = load_gbm(prod["artifact_uri"])
            if model is not None:
                model.calibrator = calibrator
                logger.info("production_gbm_loaded", version=prod.get("version"))
                return model, calibrator
    except Exception:
        logger.exception("production_gbm_load_failed")
    return None, calibrator


def build_pipeline(settings: Settings, predictor=None, calibrator=None) -> TradingPipeline:
    pred_sql = None
    port_sql = None
    outcome_sql = None
    if settings.enable_sql_persistence and settings.database_url.startswith("postgresql"):
        try:
            engine = create_engine(settings.database_url)
            factory = create_session_factory(engine)
            pred_sql = PredictionPersistenceRepository(factory)
            port_sql = PortfolioPersistenceRepository(factory)
            outcome_sql = OutcomePersistenceRepository(factory)
            logger.info("portfolio_sql_persistence_enabled")
        except Exception:
            logger.exception("portfolio_sql_persistence_unavailable")
    return TradingPipeline(
        prediction_store=DualWritePredictionStore(sql=pred_sql),
        portfolio_writer=port_sql,
        learning_store=DualWriteLearningStore(sql=outcome_sql),
        paper_days_per_cycle=1,
        predictor=predictor,
        calibrator=calibrator,
    )


def get_pipeline() -> TradingPipeline:
    if _pipeline is None:
        raise RuntimeError("Portfolio pipeline not initialized")
    return _pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    predictor, calibrator = await _resolve_predictor(settings)
    _pipeline = build_pipeline(settings, predictor=predictor, calibrator=calibrator)
    # Seed a paper cycle so the desk has a real book on boot
    try:
        await _pipeline.run_once()
        logger.info("portfolio_seed_cycle_complete")
    except Exception:
        logger.exception("portfolio_seed_cycle_failed")
    yield


app = FastAPI(title="Portfolio Desk", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "portfolio"}


@app.get("/v1/portfolio")
async def get_portfolio(pipeline: Annotated[TradingPipeline, Depends(get_pipeline)]) -> dict:
    return pipeline.latest_snapshot_payload()


@app.get("/v1/portfolio/history")
async def portfolio_history(
    pipeline: Annotated[TradingPipeline, Depends(get_pipeline)],
    limit: int = Query(50, ge=1, le=200),
) -> List[dict]:
    snaps = pipeline.portfolio.history[-limit:]
    return [
        {
            "cash": float(s.cash),
            "equity": float(s.equity),
            "drawdown": float(s.drawdown_pct),
            "totalPnl": float(s.total_pnl),
            "asOf": s.as_of.isoformat() if s.as_of else None,
            "positionCount": len(s.positions),
        }
        for s in snaps
    ]


@app.post("/v1/portfolio/run")
async def run_cycle(
    pipeline: Annotated[TradingPipeline, Depends(get_pipeline)],
    tickers: Optional[str] = Query(None, description="Comma-separated tickers"),
) -> dict:
    parsed = [t.strip().upper() for t in tickers.split(",")] if tickers else None
    result = await pipeline.run_once(parsed)
    return {**result, "portfolio": pipeline.latest_snapshot_payload()}


@app.get("/v1/portfolio/recommendations")
async def recommendations(
    pipeline: Annotated[TradingPipeline, Depends(get_pipeline)],
    limit: int = Query(8, ge=1, le=20),
) -> List[dict]:
    cards = pipeline.recommendation_payloads(limit=limit)
    return cards
