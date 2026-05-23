"""
Repository for related situations.
"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from common.database.models import RelatedSituation
from .base import BaseRepository


class RelatedSituationRepository(BaseRepository[RelatedSituation]):
    """Repository for related situation operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(RelatedSituation, db)
    
    async def get_by_source(
        self, 
        source_type: str, 
        source_id: UUID
    ) -> List[RelatedSituation]:
        """Get related situations by source."""
        result = await self.db.execute(
            select(RelatedSituation).where(
                RelatedSituation.source_type == source_type,
                RelatedSituation.source_id == source_id
            )
        )
        return list(result.scalars().all())
