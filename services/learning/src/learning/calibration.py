"""Online calibration refresh from closed-trade outcomes."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence

from ai_trading_shared.utils.logging import get_logger
from learning.domain.models import TradeOutcome
from prediction.ensemble import TemperatureCalibrator

logger = get_logger(__name__)

# Process-local last fit result (shared by API / workers in same process)
_LAST_FIT: Dict[str, float] = {"temperature": 1.2, "brier": -1.0, "samples": 0.0, "updated": 0.0}


def last_fit() -> Dict[str, float]:
    return dict(_LAST_FIT)


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
) -> Dict[str, float]:
    """Fit temperature from outcomes; no-op under min_samples."""
    global _LAST_FIT
    rows = list(window if window is not None else outcomes)
    if len(rows) < min_samples:
        result = {
            "temperature": calibrator.temperature if calibrator else _LAST_FIT["temperature"],
            "brier": -1.0,
            "samples": float(len(rows)),
            "updated": 0.0,
            "reason": "insufficient_samples",
        }
        return result

    probs = [extract_raw_prob(o) for o in rows]
    labels = [1 if o.actual_return > 0 else 0 for o in rows]
    cal = calibrator or TemperatureCalibrator(temperature=_LAST_FIT.get("temperature", 1.2))
    fit = cal.fit(probs, labels)
    _LAST_FIT = {
        "temperature": fit["temperature"],
        "brier": fit["brier"],
        "samples": fit["samples"],
        "updated": fit["updated"],
    }
    logger.info("calibrator_refreshed", **_LAST_FIT)
    return {**_LAST_FIT, "reason": "fitted"}
