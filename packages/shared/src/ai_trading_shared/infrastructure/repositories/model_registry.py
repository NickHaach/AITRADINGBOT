"""Model registry persistence — register versions and promote to production."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_shared.infrastructure.db_models import ModelRegistryRow


class ModelRegistryRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def register(
        self,
        *,
        name: str,
        version: str,
        model_type: str,
        metrics: Optional[Dict[str, Any]] = None,
        artifact_uri: Optional[str] = None,
        is_production: bool = False,
    ) -> Dict[str, Any]:
        async with self._factory() as session:
            existing = await session.scalar(
                select(ModelRegistryRow).where(
                    ModelRegistryRow.name == name,
                    ModelRegistryRow.version == version,
                )
            )
            if existing is not None:
                existing.metrics = metrics or existing.metrics
                if artifact_uri is not None:
                    existing.artifact_uri = artifact_uri
                if is_production:
                    await self._demote_others(session, name, version)
                    existing.is_production = True
                await session.commit()
                await session.refresh(existing)
                return _row(existing)

            if is_production:
                await self._demote_others(session, name, version)

            row = ModelRegistryRow(
                id=uuid4(),
                name=name,
                version=version,
                model_type=model_type,
                metrics=metrics or {},
                artifact_uri=artifact_uri,
                is_production=is_production,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _row(row)

    async def list_models(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        async with self._factory() as session:
            stmt = select(ModelRegistryRow).order_by(ModelRegistryRow.created_at.desc())
            if name:
                stmt = stmt.where(ModelRegistryRow.name == name)
            rows = (await session.scalars(stmt)).all()
            return [_row(r) for r in rows]

    async def get_production(self, name: str) -> Optional[Dict[str, Any]]:
        async with self._factory() as session:
            row = await session.scalar(
                select(ModelRegistryRow).where(
                    ModelRegistryRow.name == name,
                    ModelRegistryRow.is_production.is_(True),
                )
            )
            return _row(row) if row else None

    async def promote(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        async with self._factory() as session:
            row = await session.scalar(
                select(ModelRegistryRow).where(
                    ModelRegistryRow.name == name,
                    ModelRegistryRow.version == version,
                )
            )
            if row is None:
                return None
            await self._demote_others(session, name, version)
            row.is_production = True
            await session.commit()
            await session.refresh(row)
            return _row(row)

    @staticmethod
    async def _demote_others(session: AsyncSession, name: str, keep_version: str) -> None:
        await session.execute(
            update(ModelRegistryRow)
            .where(
                ModelRegistryRow.name == name,
                ModelRegistryRow.version != keep_version,
            )
            .values(is_production=False)
        )


def _row(row: ModelRegistryRow) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.name,
        "version": row.version,
        "model_type": row.model_type,
        "metrics": row.metrics or {},
        "artifact_uri": row.artifact_uri,
        "is_production": row.is_production,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
