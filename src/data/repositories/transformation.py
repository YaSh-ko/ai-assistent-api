"""
Repository for transformations.
"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from common.database.models import Transformation
from .base import BaseRepository


class TransformationRepository(BaseRepository[Transformation]):
    """Repository for transformation operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Transformation, db)
    
    async def get_by_source(
        self, 
        source_type: str, 
        source_id: UUID
    ) -> List[Transformation]:
        """Get transformations by source."""
        result = await self.db.execute(
            select(Transformation).where(
                Transformation.source_type == source_type,
                Transformation.source_id == source_id
            )
        )
        return list(result.scalars().all())
