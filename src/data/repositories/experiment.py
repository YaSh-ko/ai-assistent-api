"""
Repository for experiments.
"""
from typing import List

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.models import Experiment

from .base import BaseRepository


class ExperimentRepository(BaseRepository[Experiment]):
    """Repository for experiment operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(Experiment, db)

    async def get_by_user_id(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Experiment]:
        result = await self.db.execute(
            select(Experiment)
            .where(Experiment.user_id == user_id)
            .order_by(desc(Experiment.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
