"""Model registry repository tests (SQLite)."""

from __future__ import annotations

import pytest

from ai_trading_shared.infrastructure.database import create_engine, create_session_factory
from ai_trading_shared.infrastructure.db_models import ModelRegistryRow
from ai_trading_shared.infrastructure.repositories.model_registry import ModelRegistryRepository


@pytest.fixture
async def registry(tmp_path):
    db_path = tmp_path / "models.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: ModelRegistryRow.__table__.create(c, checkfirst=True))
    factory = create_session_factory(engine)
    yield ModelRegistryRepository(factory)
    await engine.dispose()


@pytest.mark.asyncio
async def test_register_and_promote(registry: ModelRegistryRepository) -> None:
    a = await registry.register(
        name="gbm_direction",
        version="v1",
        model_type="gbm",
        metrics={"train_accuracy": 0.6},
    )
    assert a["is_production"] is False
    await registry.register(
        name="gbm_direction",
        version="v2",
        model_type="gbm",
        metrics={"train_accuracy": 0.7},
    )
    promoted = await registry.promote("gbm_direction", "v2")
    assert promoted is not None
    assert promoted["is_production"] is True
    prod = await registry.get_production("gbm_direction")
    assert prod is not None
    assert prod["version"] == "v2"
    listed = await registry.list_models(name="gbm_direction")
    assert len(listed) == 2
    assert sum(1 for m in listed if m["is_production"]) == 1
