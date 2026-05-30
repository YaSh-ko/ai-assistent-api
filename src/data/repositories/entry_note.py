"""Repository for entry notes (append-only observation supplements)."""
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.models import EntryNote
from .base import BaseRepository


class EntryNoteRepository(BaseRepository[EntryNote]):
    def __init__(self, db: AsyncSession):
        super().__init__(EntryNote, db)

    async def get_by_entry_id(self, entry_id: UUID) -> List[EntryNote]:
        result = await self.db.execute(
            select(EntryNote)
            .where(EntryNote.entry_id == entry_id)
            .order_by(EntryNote.created_at.asc())
        )
        return list(result.scalars().all())
