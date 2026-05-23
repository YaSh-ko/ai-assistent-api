"""
Repository for messages.
"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID

from common.database.models import Message
from .base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    """Repository for message operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Message, db)
    
    async def get_by_conversation_id(
        self, 
        conversation_id: UUID, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Message]:
        """Get messages by conversation ID."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
