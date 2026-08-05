"""Online calibration refresh from closed-trade outcomes.

Temperature is shared across processes via Redis when available, with an
in-memory fallback for offline / unit tests.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from ai_trading_shared.config import get_settings
from ai_trading_shared.infrastructure.redis_kv import CALIBRATION_KEY, RedisJsonStore
from ai_trading_shared.utils.logging import get_logger
from learning.domain.models import TradeOutcome
from prediction.ensemble import TemperatureCalibrator

logger = get_logger(__name__)

# Process-local last fit result (fallback when Redis is down)
_LAST_FIT: Dict[str, float] = {"temperature": 1.2, "brier": -1.0, "samples": 0.0, "updated": 0.0}


def _store() -> RedisJsonStore:
    return RedisJsonStore(get_settings().redis_url)


def last_fit() -> Dict[str, float]:
    remote = _store().get_json(CALIBRATION_KEY)
    if remote:
        try:
            return {
                "temperature": float(remote.get("temperature", 1.2)),
                "brier": float(remote.get("brier", -1.0)),
                "samples": float(remote.get("samples", 0.0)),
                "updated": float(remote.get("updated", 0.0)),
            }
        except Exception:
            pass
    return dict(_LAST_FIT)


def _persist(fit: Dict[str, float]) -> None:
    global _LAST_FIT
    _LAST_FIT = dict(fit)
    written = _store().set_json(CALIBRATION_KEY, fit)
    if written:
        logger.info("calibration_persisted_redis", temperature=fit.get("temperature"))


def extract_raw_prob(outcome: TradeOutcome) -> float:
    try:
        payload = json.loads(outcome.notes or "{}")
        if "direction_raw" in payload:
            return float(payload["direction_raw"])
    except Exception:
        pass
    return float(outcome.probability_success)


def refresh_calibrator(
    outcomes: Sequence[TradeOutcome],
    calibrator: Optional[TemperatureCalibrator] = None,
    *,
    min_samples: int = 30,
    window: Optional[List[TradeOutcome]] = None,
) -> Dict[str, Any]:
    """Fit temperature from outcomes; no-op under min_samples."""
    current = last_fit()
    rows = list(window if window is not None else outcomes)
    if len(rows) < min_samples:
        return {
            "temperature": calibrator.temperature if calibrator else current["temperature"],
            "brier": -1.0,
            "samples": float(len(rows)),
            "updated": 0.0,
            "reason": "insufficient_samples",
        }

    probs = [extract_raw_prob(o) for o in rows]
    labels = [1 if o.actual_return > 0 else 0 for o in rows]
    cal = calibrator or TemperatureCalibrator(temperature=current.get("temperature", 1.2))
    fit = cal.fit(probs, labels)
    payload = {
        "temperature": fit["temperature"],
        "brier": fit["brier"],
        "samples": fit["samples"],
        "updated": fit["updated"],
    }
    _persist(payload)
    logger.info("calibrator_refreshed", **payload)
    return {**payload, "reason": "fitted"}
