"""
Repository for goals.
"""
from typing import List

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.models import Goal

from .base import BaseRepository


class GoalRepository(BaseRepository[Goal]):
    """Repository for goal operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(Goal, db)

    async def get_by_user_id(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Goal]:
        result = await self.db.execute(
            select(Goal)
            .where(Goal.user_id == user_id)
            .order_by(desc(Goal.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
