"""
Repository for entries.
"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import date

from common.database.models import Entry
from .base import BaseRepository


class EntryRepository(BaseRepository[Entry]):
    """Repository for entry operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Entry, db)
    
    async def get_by_user_id(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Entry]:
        """Get entries by user ID."""
        result = await self.db.execute(
            select(Entry)
            .where(Entry.user_id == user_id)
            .order_by(desc(Entry.event_date))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_recent(self, user_id: str, limit: int = 10) -> List[Entry]:
        """Get recent entries."""
        return await self.get_by_user_id(user_id, skip=0, limit=limit)
