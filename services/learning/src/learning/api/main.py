"""Learning Engine FastAPI app."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from ai_trading_shared.config import Settings, get_settings
from ai_trading_shared.domain.enums import SignalAction
from ai_trading_shared.infrastructure.database import create_engine, create_session_factory
from ai_trading_shared.infrastructure.repositories.model_registry import ModelRegistryRepository
from ai_trading_shared.infrastructure.repositories.persistence import OutcomePersistenceRepository
from ai_trading_shared.utils.logging import configure_logging, get_logger
from learning.application.engine import LearningEngine
from learning.infrastructure.dual_write import DualWriteLearningStore

logger = get_logger(__name__)
_store: Optional[DualWriteLearningStore] = None
_registry: Optional[ModelRegistryRepository] = None


class RecordRequest(BaseModel):
    signal_id: UUID
    trade_id: Optional[UUID] = None
    ticker: str
    action: SignalAction
    predicted_return: float
    probability_success: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    model_versions: List[str] = Field(default_factory=list)
    actual_return: float
    holding_days: int = Field(ge=0)
    pnl: float
    notes: str = ""


class RegisterModelRequest(BaseModel):
    name: str
    version: str
    model_type: str = "gbm"
    metrics: dict = Field(default_factory=dict)
    artifact_uri: Optional[str] = None
    is_production: bool = False


def build_store(settings: Settings) -> DualWriteLearningStore:
    sql = None
    if settings.enable_sql_persistence and settings.database_url.startswith("postgresql"):
        try:
            engine = create_engine(settings.database_url)
            sql = OutcomePersistenceRepository(create_session_factory(engine))
            logger.info("learning_sql_dual_write_enabled")
        except Exception:
            logger.exception("learning_sql_dual_write_unavailable")
    return DualWriteLearningStore(engine=LearningEngine(), sql=sql)


def build_registry(settings: Settings) -> Optional[ModelRegistryRepository]:
    if not (settings.enable_sql_persistence and settings.database_url.startswith("postgresql")):
        return None
    try:
        engine = create_engine(settings.database_url)
        return ModelRegistryRepository(create_session_factory(engine))
    except Exception:
        logger.exception("model_registry_unavailable")
        return None


def get_store() -> DualWriteLearningStore:
    if _store is None:
        raise RuntimeError("Learning store not initialized")
    return _store


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store, _registry
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)
    _store = build_store(settings)
    _registry = build_registry(settings)
    logger.info("learning_started")
    yield


app = FastAPI(title="Learning Engine", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "learning"}


@app.post("/v1/learning/outcomes")
async def record_outcome(
    body: RecordRequest,
    store: Annotated[DualWriteLearningStore, Depends(get_store)],
) -> dict:
    outcome = await store.record_closed_trade(**body.model_dump())
    return outcome.model_dump(mode="json")


@app.get("/v1/learning/outcomes")
async def list_outcomes(
    store: Annotated[DualWriteLearningStore, Depends(get_store)],
    ticker: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
) -> List[dict]:
    return [o.model_dump(mode="json") for o in store.list_outcomes(ticker=ticker, limit=limit)]


@app.get("/v1/learning/report")
async def report(
    store: Annotated[DualWriteLearningStore, Depends(get_store)],
    model_name: str = "all",
    window_days: Optional[int] = Query(None, ge=1, le=365),
) -> dict:
    return store.evaluate(model_name, window_days=window_days).model_dump(mode="json")


@app.post("/v1/models/register")
async def register_model(body: RegisterModelRequest) -> dict:
    if _registry is None:
        raise HTTPException(status_code=503, detail="Model registry requires ENABLE_SQL_PERSISTENCE")
    return await _registry.register(**body.model_dump())


@app.get("/v1/models")
async def list_models(name: Optional[str] = None) -> List[dict]:
    if _registry is None:
        raise HTTPException(status_code=503, detail="Model registry requires ENABLE_SQL_PERSISTENCE")
    return await _registry.list_models(name=name)


@app.post("/v1/models/{name}/versions/{version}/promote")
async def promote_model(name: str, version: str) -> dict:
    if _registry is None:
        raise HTTPException(status_code=503, detail="Model registry requires ENABLE_SQL_PERSISTENCE")
    promoted = await _registry.promote(name, version)
    if promoted is None:
        raise HTTPException(status_code=404, detail="Model version not found")
    return promoted


@app.post("/v1/models/auto-promote")
async def auto_promote(
    store: Annotated[DualWriteLearningStore, Depends(get_store)],
    model_name: str = Query(..., description="Registered model name to evaluate"),
    version: str = Query(...),
    window_days: int = Query(30, ge=1, le=365),
) -> dict:
    """Promote when rolling eval meets LearningEngine thresholds."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="Model registry requires ENABLE_SQL_PERSISTENCE")
    report = store.evaluate(model_name, window_days=window_days)
    eligible = LearningEngine.meets_promotion_thresholds(report)
    if not eligible:
        return {
            "promoted": False,
            "reason": "thresholds_not_met",
            "report": report.model_dump(mode="json"),
        }
    # Ensure version exists (register stub metrics from report if missing)
    await _registry.register(
        name=model_name,
        version=version,
        model_type="ensemble",
        metrics=report.model_dump(mode="json"),
        is_production=False,
    )
    promoted = await _registry.promote(model_name, version)
    return {"promoted": True, "model": promoted, "report": report.model_dump(mode="json")}


@app.get("/v1/learning/calibration")
async def get_calibration() -> dict:
    from learning.calibration import last_fit

    return last_fit()


@app.post("/v1/learning/calibration/refresh")
async def refresh_calibration(
    store: Annotated[DualWriteLearningStore, Depends(get_store)],
    min_samples: int = Query(30, ge=5, le=500),
) -> dict:
    from learning.calibration import refresh_calibrator
    from prediction.ensemble import TemperatureCalibrator

    outcomes = store.list_outcomes(limit=5000)
    return refresh_calibrator(outcomes, calibrator=TemperatureCalibrator(), min_samples=min_samples)


class TrainGbmRequest(BaseModel):
    version: str = "v1"
    n_samples: int = Field(80, ge=20, le=5000)
    promote: bool = False
    source: str = Field("synthetic", description="synthetic | outcomes")


@app.post("/v1/models/gbm/train")
async def train_gbm(
    body: TrainGbmRequest,
    store: Annotated[DualWriteLearningStore, Depends(get_store)],
) -> dict:
    """Train GBM, save artifact, register in model registry.

    source=synthetic uses generated rows; source=outcomes rebuilds from closed trades
    that stored FEATURE_NAMES in notes.
    """
    from learning.calibration import last_fit
    from learning.training_rows import outcomes_to_training_rows
    from prediction.artifacts import save_gbm
    from prediction.ensemble import TemperatureCalibrator
    from prediction.gbm_model import GradientBoostDirectionModel, synthesize_training_rows

    fit = last_fit()
    model = GradientBoostDirectionModel(
        calibrator=TemperatureCalibrator(temperature=float(fit.get("temperature") or 1.1))
    )
    if body.source == "outcomes":
        rows = outcomes_to_training_rows(store.list_outcomes(limit=5000))
        if len(rows) < 10:
            raise HTTPException(
                status_code=400,
                detail=f"Need ≥10 outcomes with feature vectors (got {len(rows)})",
            )
        metrics = model.fit(rows)
        metrics["source"] = "outcomes"
    else:
        metrics = model.fit(synthesize_training_rows(body.n_samples))
        metrics["source"] = "synthetic"
    uri = save_gbm(model, name="gbm_direction_v1", version=body.version)
    registered = None
    if _registry is not None:
        registered = await _registry.register(
            name="gbm_direction_v1",
            version=body.version,
            model_type="gbm",
            metrics=metrics,
            artifact_uri=uri,
            is_production=body.promote,
        )
    elif body.promote:
        raise HTTPException(status_code=503, detail="Promote requires ENABLE_SQL_PERSISTENCE")
    return {
        "trained": True,
        "metrics": metrics,
        "artifact_uri": uri,
        "registered": registered,
    }
