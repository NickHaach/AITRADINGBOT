"""Celery tasks for Learning Engine rolling evaluation."""

from __future__ import annotations

import asyncio

from ai_trading_shared.config import get_settings
from ai_trading_shared.domain.enums import SignalAction
from ai_trading_shared.infrastructure.database import create_engine, create_session_factory
from ai_trading_shared.infrastructure.repositories.model_registry import ModelRegistryRepository
from ai_trading_shared.infrastructure.repositories.persistence import OutcomePersistenceRepository
from ai_trading_shared.utils.logging import configure_logging, get_logger
from learning.application.engine import LearningEngine
from learning.domain.models import TradeOutcome
from learning.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _evaluate_window(window_days: int, model_name: str) -> dict:
    settings = get_settings()
    engine = LearningEngine()

    if settings.enable_sql_persistence and settings.database_url.startswith("postgresql"):
        sql_engine = create_engine(settings.database_url)
        factory = create_session_factory(sql_engine)
        outcomes_repo = OutcomePersistenceRepository(factory)
        rows = await outcomes_repo.list_for_eval()
        hydrated = []
        for row in rows:
            try:
                action = SignalAction(row["action"]) if isinstance(row["action"], str) else row["action"]
            except Exception:
                action = SignalAction.HOLD
            hydrated.append(
                TradeOutcome(
                    id=row["id"],
                    signal_id=row["signal_id"],
                    trade_id=row.get("trade_id"),
                    ticker=row["ticker"],
                    action=action,
                    predicted_direction=row["predicted_direction"],
                    predicted_return=row["predicted_return"],
                    probability_success=row["probability_success"],
                    confidence=row["confidence"],
                    model_versions=row.get("model_versions") or [],
                    actual_return=row["actual_return"],
                    holding_days=row["holding_days"],
                    correct_direction=row["correct_direction"],
                    pnl=row["pnl"],
                    closed_at=row["closed_at"],
                    notes=row.get("notes") or "",
                )
            )
        engine.replace_outcomes(hydrated)
        await sql_engine.dispose()

    report = engine.evaluate(model_name, window_days=window_days)
    payload = {
        "window_days": window_days,
        "report": report.model_dump(mode="json"),
        "promotion_eligible": LearningEngine.meets_promotion_thresholds(report),
    }
    logger.info(
        "learning_window_evaluated",
        sample_size=report.sample_size,
        direction_accuracy=report.direction_accuracy,
        window_days=window_days,
    )
    return payload


@celery_app.task(name="learning.workers.tasks.evaluate_window_task")
def evaluate_window_task(window_days: int = 7, model_name: str = "all") -> dict:
    settings = get_settings()
    configure_logging(settings.log_level)
    return asyncio.run(_evaluate_window(window_days=window_days, model_name=model_name))


@celery_app.task(name="learning.workers.tasks.auto_promote_task")
def auto_promote_task(
    model_name: str,
    version: str,
    window_days: int = 30,
) -> dict:
    """Evaluate SQL outcomes and promote when thresholds pass."""

    async def _run() -> dict:
        settings = get_settings()
        if not (settings.enable_sql_persistence and settings.database_url.startswith("postgresql")):
            return {"promoted": False, "reason": "sql_persistence_required"}
        payload = await _evaluate_window(window_days=window_days, model_name=model_name)
        report = payload["report"]
        if not payload["promotion_eligible"]:
            return {"promoted": False, "reason": "thresholds_not_met", **payload}
        sql_engine = create_engine(settings.database_url)
        registry = ModelRegistryRepository(create_session_factory(sql_engine))
        await registry.register(
            name=model_name,
            version=version,
            model_type="ensemble",
            metrics=report,
            is_production=False,
        )
        promoted = await registry.promote(model_name, version)
        await sql_engine.dispose()
        return {"promoted": True, "model": promoted, **payload}

    settings = get_settings()
    configure_logging(settings.log_level)
    return asyncio.run(_run())


@celery_app.task(name="learning.workers.tasks.refresh_calibration_task")
def refresh_calibration_task(window_days: int = 30, min_samples: int = 30) -> dict:
    """Fit temperature calibrator from SQL outcomes (rolling window)."""

    async def _run() -> dict:
        from datetime import datetime, timedelta, timezone

        from learning.calibration import refresh_calibrator
        from prediction.ensemble import TemperatureCalibrator

        settings = get_settings()
        engine = LearningEngine()
        if settings.enable_sql_persistence and settings.database_url.startswith("postgresql"):
            sql_engine = create_engine(settings.database_url)
            factory = create_session_factory(sql_engine)
            outcomes_repo = OutcomePersistenceRepository(factory)
            rows = await outcomes_repo.list_for_eval()
            hydrated = []
            for row in rows:
                try:
                    action = (
                        SignalAction(row["action"]) if isinstance(row["action"], str) else row["action"]
                    )
                except Exception:
                    action = SignalAction.HOLD
                hydrated.append(
                    TradeOutcome(
                        id=row["id"],
                        signal_id=row["signal_id"],
                        trade_id=row.get("trade_id"),
                        ticker=row["ticker"],
                        action=action,
                        predicted_direction=row["predicted_direction"],
                        predicted_return=row["predicted_return"],
                        probability_success=row["probability_success"],
                        confidence=row["confidence"],
                        model_versions=row.get("model_versions") or [],
                        actual_return=row["actual_return"],
                        holding_days=row["holding_days"],
                        correct_direction=row["correct_direction"],
                        pnl=row["pnl"],
                        closed_at=row["closed_at"],
                        notes=row.get("notes") or "",
                    )
                )
            engine.replace_outcomes(hydrated)
            await sql_engine.dispose()

        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        window = [
            o
            for o in engine.list_outcomes(limit=5000)
            if (o.closed_at.replace(tzinfo=timezone.utc) if o.closed_at.tzinfo is None else o.closed_at)
            >= cutoff
        ]
        cal = TemperatureCalibrator()
        result = refresh_calibrator(window, calibrator=cal, min_samples=min_samples)
        logger.info("calibration_task_done", **{k: result.get(k) for k in ("temperature", "samples", "updated")})
        return result

    settings = get_settings()
    configure_logging(settings.log_level)
    return asyncio.run(_run())
