"""
Repository for conversations.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID

from common.database.models import Conversation
from .base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for conversation operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Conversation, db)
    
    async def get_by_user_id(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Conversation]:
        """Get conversations by user ID."""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.last_active_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_by_thread_id(self, thread_id: str) -> Optional[Conversation]:
        """Get conversation by thread ID."""
        result = await self.db.execute(
            select(Conversation).where(Conversation.thread_id == thread_id)
        )
        return result.scalar_one_or_none()
    
    async def get_recent(self, user_id: str, limit: int = 10) -> List[Conversation]:
        """Get recent conversations."""
        return await self.get_by_user_id(user_id, skip=0, limit=limit)

    async def create_with_metadata(
        self, user_id: str, thread_id: str, meta_data: dict, title: str = "Новый чат"
    ) -> Conversation:
        """Create a new conversation with pre-set metadata (e.g. category)."""
        conversation = Conversation(
            user_id=user_id,
            thread_id=thread_id,
            meta_data=meta_data,
            title=title,
        )
        return await self.create(conversation)
