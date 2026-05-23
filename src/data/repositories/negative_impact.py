"""
Repository for negative impacts.
"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from common.database.models import NegativeImpact
from .base import BaseRepository


class NegativeImpactRepository(BaseRepository[NegativeImpact]):
    """Repository for negative impact operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(NegativeImpact, db)
    
    async def get_by_source(
        self, 
        source_type: str, 
        source_id: UUID
    ) -> List[NegativeImpact]:
        """Get negative impacts by source."""
        result = await self.db.execute(
            select(NegativeImpact).where(
                NegativeImpact.source_type == source_type,
                NegativeImpact.source_id == source_id
            )
        )
        return list(result.scalars().all())
