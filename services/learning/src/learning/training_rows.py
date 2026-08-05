"""Rebuild GBM training rows from closed-trade outcome notes."""

from __future__ import annotations

import json
from typing import List, Optional, Sequence, Tuple

from learning.domain.models import TradeOutcome
from prediction.gbm_model import FEATURE_NAMES


def outcome_to_training_row(outcome: TradeOutcome) -> Optional[Tuple[List[float], int]]:
    """Extract FEATURE_NAMES vector + up/down label from outcome notes."""
    try:
        payload = json.loads(outcome.notes or "{}")
    except Exception:
        return None
    features = payload.get("features") or {}
    if not isinstance(features, dict):
        return None
    vector: List[float] = []
    for name in FEATURE_NAMES:
        if name not in features:
            return None
        try:
            vector.append(float(features[name]))
        except (TypeError, ValueError):
            return None
    label = 1 if outcome.actual_return > 0 else 0
    return vector, label


def outcomes_to_training_rows(
    outcomes: Sequence[TradeOutcome],
) -> List[Tuple[List[float], int]]:
    rows: List[Tuple[List[float], int]] = []
    for outcome in outcomes:
        row = outcome_to_training_row(outcome)
        if row is not None:
            rows.append(row)
    return rows
