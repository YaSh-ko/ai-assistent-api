"""
Repository for experiments.
"""
from typing import List
from uuid import UUID

from sqlalchemy import case, desc, select
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

    async def get_by_goal_id(self, goal_id: UUID, user_id: str) -> List[Experiment]:
        phase_order = case(
            (Experiment.phase == "now", 0),
            (Experiment.phase == "next", 1),
            (Experiment.phase == "backlog", 2),
            else_=3,
        )
        status_order = case(
            (Experiment.status == "completed", 1),
            else_=0,
        )
        result = await self.db.execute(
            select(Experiment)
            .where(Experiment.goal_id == goal_id, Experiment.user_id == user_id)
            .order_by(status_order, phase_order, desc(Experiment.created_at))
        )
        return list(result.scalars().all())
