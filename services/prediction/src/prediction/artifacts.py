"""Local filesystem GBM artifact persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from ai_trading_shared.config import get_settings
from ai_trading_shared.utils.logging import get_logger
from prediction.ensemble import TemperatureCalibrator
from prediction.gbm_model import GradientBoostDirectionModel

logger = get_logger(__name__)


def artifact_root() -> Path:
    settings = get_settings()
    root = Path(getattr(settings, "model_artifact_dir", None) or "artifacts")
    root.mkdir(parents=True, exist_ok=True)
    return root


def gbm_artifact_path(name: str, version: str) -> Path:
    safe_name = name.replace("/", "_")
    safe_version = version.replace("/", "_")
    path = artifact_root() / "gbm" / safe_name
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{safe_version}.joblib"


def path_to_uri(path: Path) -> str:
    return path.resolve().as_uri()


def uri_to_path(uri: str) -> Path:
    if uri.startswith("file:"):
        parsed = urlparse(uri)
        return Path(parsed.path)
    return Path(uri)


def save_gbm(model: GradientBoostDirectionModel, *, name: str, version: str) -> str:
    """Persist model weights + calibrator; returns file:// URI."""
    import joblib

    if not model.is_trained:
        raise ValueError("Cannot save untrained GBM")
    path = gbm_artifact_path(name, version)
    payload = {
        "backend": model._backend,
        "model": model._model,
        "temperature": model.calibrator.temperature,
        "name": model.name,
    }
    joblib.dump(payload, path)
    uri = path_to_uri(path)
    logger.info("gbm_artifact_saved", path=str(path), uri=uri)
    return uri


def load_gbm(uri: str) -> Optional[GradientBoostDirectionModel]:
    """Load GBM from file:// URI or local path. Returns None on failure."""
    import joblib

    try:
        path = uri_to_path(uri)
        if not path.exists():
            logger.warning("gbm_artifact_missing", path=str(path))
            return None
        payload = joblib.load(path)
        model = GradientBoostDirectionModel(
            calibrator=TemperatureCalibrator(temperature=float(payload.get("temperature", 1.1)))
        )
        model._model = payload["model"]
        model._backend = payload.get("backend", "sklearn")
        if payload.get("name"):
            model.name = payload["name"]
        return model
    except Exception:
        logger.exception("gbm_artifact_load_failed", uri=uri)
        return None
