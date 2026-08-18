"""Portfolio desk FastAPI — live paper book + pipeline runner."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ai_trading_shared.config import Settings, get_settings
from ai_trading_shared.infrastructure.database import create_engine, create_session_factory
from ai_trading_shared.infrastructure.repositories.model_registry import ModelRegistryRepository
from ai_trading_shared.infrastructure.repositories.persistence import (
    OutcomePersistenceRepository,
    PortfolioPersistenceRepository,
    PredictionPersistenceRepository,
)
from ai_trading_shared.utils.logging import configure_logging, get_logger
from execution.brokers.alpaca import AlpacaBroker, PAPER_BASE, broker_status_payload
from execution.pipeline import TradingPipeline
from execution.service import ExecutionService, PaperBroker
from learning.infrastructure.dual_write import DualWriteLearningStore
from portfolio.autopilot import AutopilotConfig, AutopilotController
from prediction.artifacts import load_gbm
from prediction.infrastructure.dual_write import DualWritePredictionStore
from pydantic import BaseModel, Field

logger = get_logger(__name__)
_pipeline: Optional[TradingPipeline] = None
_autopilot: Optional[AutopilotController] = None
# Runtime Alpaca keys connected from the desk (not written to disk).
_runtime_alpaca: Optional[dict] = None


class BrokerConnectBody(BaseModel):
    api_key: str = Field(min_length=8, max_length=128)
    secret_key: str = Field(min_length=8, max_length=128)
    paper: bool = True


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
        settings=settings,
    )


def get_pipeline() -> TradingPipeline:
    if _pipeline is None:
        raise RuntimeError("Portfolio pipeline not initialized")
    return _pipeline


def get_autopilot() -> AutopilotController:
    if _autopilot is None:
        raise RuntimeError("Autopilot not initialized")
    return _autopilot


async def execute_trading_cycle(tickers: Optional[str] = None) -> dict:
    """Shared cycle runner for manual Run + autopilot."""
    pipeline = get_pipeline()
    if pipeline.risk.config.kill_switch:
        raise HTTPException(status_code=423, detail="Kill switch armed — trading paused")
    parsed = [t.strip().upper() for t in tickers.split(",")] if tickers else None
    universe = parsed or ["AAPL", "MSFT", "NVDA", "XOM", "JPM"]
    from execution.intelligence import gather_intelligence

    intel = await gather_intelligence(universe)
    result = await pipeline.run_once(
        universe,
        news_by_ticker=intel.news_by_ticker,
        announcement_impact=intel.announcement_impact,
        social_by_ticker=intel.social_by_ticker,
        analyst_by_ticker=intel.analyst_by_ticker,
        macro_bias=intel.macro_bias,
        geo_bias=intel.geo_bias,
        intelligence_summary=intel.summary(),
    )
    return {**result, "portfolio": pipeline.latest_snapshot_payload()}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline, _autopilot
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    predictor, calibrator = await _resolve_predictor(settings)
    _pipeline = build_pipeline(settings, predictor=predictor, calibrator=calibrator)

    def set_kill(armed: bool) -> None:
        _pipeline.risk.config.kill_switch = bool(armed)

    async def autopilot_cycle() -> dict:
        return await execute_trading_cycle(_autopilot.config.tickers if _autopilot else None)

    _autopilot = AutopilotController(run_cycle=autopilot_cycle, set_kill_switch=set_kill)

    # Seed a paper cycle so the desk has a real book on boot (with multi-source intel)
    try:
        from execution.intelligence import gather_intelligence

        universe = ["AAPL", "MSFT", "NVDA", "XOM", "JPM"]
        intel = await gather_intelligence(universe, include_web=False)
        await _pipeline.run_once(
            universe,
            news_by_ticker=intel.news_by_ticker,
            announcement_impact=intel.announcement_impact,
            social_by_ticker=intel.social_by_ticker,
            analyst_by_ticker=intel.analyst_by_ticker,
            macro_bias=intel.macro_bias,
            geo_bias=intel.geo_bias,
            intelligence_summary=intel.summary(),
        )
        logger.info("portfolio_seed_cycle_complete", sources=intel.sources_used)
    except Exception:
        logger.exception("portfolio_seed_cycle_failed")
    yield
    if _autopilot is not None:
        await _autopilot.shutdown()


app = FastAPI(title="Portfolio Desk", version="0.1.0", lifespan=lifespan)
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "portfolio"}


@app.get("/v1/portfolio/broker")
async def broker_status(
    pipeline: Annotated[TradingPipeline, Depends(get_pipeline)],
) -> dict:
    settings = get_settings()
    status = broker_status_payload(pipeline.broker, settings)
    if _runtime_alpaca:
        status["has_alpaca_keys"] = True
        status["connected_via"] = "desk"
    account = None
    error = None
    if getattr(pipeline.broker, "name", None) == "alpaca" and hasattr(
        pipeline.broker, "ping_account"
    ):
        try:
            account = await pipeline.broker.ping_account()
            status["account_ok"] = True
            status["connected"] = True
            status["mode"] = "alpaca_paper" if account.get("paper") else "live"
        except Exception as exc:  # noqa: BLE001 — surface connect errors to UI
            status["account_ok"] = False
            error = str(exc)[:300]
    else:
        status["account_ok"] = False
    if error:
        status["error"] = error
    if account:
        status["account"] = account
    return status


@app.post("/v1/portfolio/broker/connect")
async def broker_connect(
    body: BrokerConnectBody,
    pipeline: Annotated[TradingPipeline, Depends(get_pipeline)],
) -> dict:
    """Hot-connect Alpaca from the desk (paper by default)."""
    global _runtime_alpaca
    settings = get_settings()
    base = PAPER_BASE if body.paper else "https://api.alpaca.markets"
    live_enabled = (not body.paper) and settings.enable_live_trading and settings.execution_mode == "live"
    if not body.paper and not live_enabled:
        raise HTTPException(
            status_code=400,
            detail=(
                "Live Alpaca requires EXECUTION_MODE=live and ENABLE_LIVE_TRADING=true "
                "in .env, then restart. Use paper=true for practice money."
            ),
        )
    broker = AlpacaBroker(
        api_key=body.api_key.strip(),
        secret_key=body.secret_key.strip(),
        base_url=base,
        live_enabled=live_enabled,
    )
    try:
        account = await broker.ping_account()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Alpaca auth failed: {exc}") from exc

    pipeline.broker = broker
    pipeline.execution = ExecutionService(broker, live_enabled=True)
    _runtime_alpaca = {"paper": body.paper, "base_url": base}
    logger.info(
        "alpaca_connected_from_desk",
        paper=body.paper,
        live=not body.paper,
        status=account.get("status"),
    )
    status = broker_status_payload(broker, settings)
    status["account_ok"] = True
    status["connected"] = True
    status["connected_via"] = "desk"
    status["has_alpaca_keys"] = True
    status["account"] = account
    status["mode"] = "alpaca_paper" if body.paper else "live"
    status["live_trading_armed"] = bool(live_enabled and not body.paper)
    status["live_connect_allowed"] = bool(
        settings.enable_live_trading and settings.execution_mode == "live"
    )
    return status


@app.post("/v1/portfolio/broker/disconnect")
async def broker_disconnect(
    pipeline: Annotated[TradingPipeline, Depends(get_pipeline)],
) -> dict:
    global _runtime_alpaca
    pipeline.broker = PaperBroker()
    pipeline.execution = ExecutionService(pipeline.broker, live_enabled=False)
    _runtime_alpaca = None
    settings = get_settings()
    status = broker_status_payload(pipeline.broker, settings)
    status["account_ok"] = False
    status["connected"] = False
    status["connected_via"] = "local"
    return status


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
    tickers: Optional[str] = Query(None, description="Comma-separated tickers"),
) -> dict:
    return await execute_trading_cycle(tickers)


@app.get("/v1/portfolio/recommendations")
async def recommendations(
    pipeline: Annotated[TradingPipeline, Depends(get_pipeline)],
    limit: int = Query(8, ge=1, le=20),
) -> List[dict]:
    cards = pipeline.recommendation_payloads(limit=limit)
    return cards


@app.get("/v1/portfolio/blotter")
async def blotter(
    pipeline: Annotated[TradingPipeline, Depends(get_pipeline)],
    limit: int = Query(80, ge=1, le=300),
) -> dict:
    return {
        "events": pipeline.blotter_payloads(limit=limit),
        "cycles": pipeline.cycle_history_payloads(limit=min(20, limit)),
    }


@app.get("/v1/portfolio/journal")
async def journal(
    pipeline: Annotated[TradingPipeline, Depends(get_pipeline)],
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    return pipeline.journal_payload(limit=limit)


@app.get("/v1/portfolio/autopilot")
async def autopilot_get(autopilot: Annotated[AutopilotController, Depends(get_autopilot)]) -> dict:
    return autopilot.status().model_dump(mode="json")


@app.post("/v1/portfolio/autopilot")
async def autopilot_update(
    body: AutopilotConfig,
    autopilot: Annotated[AutopilotController, Depends(get_autopilot)],
) -> dict:
    return autopilot.apply_config(body).model_dump(mode="json")


@app.post("/v1/portfolio/autopilot/start")
async def autopilot_start(autopilot: Annotated[AutopilotController, Depends(get_autopilot)]) -> dict:
    return autopilot.start().model_dump(mode="json")


@app.post("/v1/portfolio/autopilot/stop")
async def autopilot_stop(autopilot: Annotated[AutopilotController, Depends(get_autopilot)]) -> dict:
    return autopilot.stop().model_dump(mode="json")
