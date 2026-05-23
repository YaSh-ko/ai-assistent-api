"""
Message endpoints.
"""
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, delete
from common.database.models import Message, MessageReaction
from src.api.v1.deps import get_current_user_id
from src.core.database import get_db
from src.data.repositories.conversation import ConversationRepository
from src.data.repositories.message import MessageRepository
from src.api.v1.schemas.messages import (
    MessageResponse,
    MessageListResponse,
    MessageCreateRequest,
    MessageReactionRequest,
    MessageReactionResponse,
)

router = APIRouter()


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages(
    conversation_id: UUID,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
):
    """Get messages for a conversation."""
    # Verify conversation belongs to user
    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_by_id(conversation_id)
    if not conversation or conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    repo = MessageRepository(db)
    messages = await repo.get_by_conversation_id(conversation_id, skip=skip, limit=limit)
    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in messages]
    )


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    conversation_id: UUID,
    request: MessageCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new message."""
    # Verify conversation belongs to user
    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_by_id(conversation_id)
    if not conversation or conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    message = Message(
        conversation_id=conversation_id,
        user_id=user_id,
        role=request.role,
        content=request.content,
        meta_data=json.dumps(request.meta_data) if request.meta_data else None
    )
    
    repo = MessageRepository(db)
    created = await repo.create(message)
    return MessageResponse.model_validate(created)


@router.post("/messages/{message_id}/reactions", response_model=MessageReactionResponse, status_code=status.HTTP_201_CREATED)
async def add_reaction(
    message_id: UUID,
    request: MessageReactionRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Add a reaction to a message."""
    # Verify message exists and belongs to user's conversation
    msg_repo = MessageRepository(db)
    message = await msg_repo.get_by_id(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_by_id(message.conversation_id)
    if not conversation or conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    reaction = MessageReaction(
        message_id=message_id,
        user_id=user_id,
        reaction_type=request.reaction_type,
        emoji=request.emoji
    )
    
    db.add(reaction)
    await db.commit()
    await db.refresh(reaction)
    
    return MessageReactionResponse.model_validate(reaction)


@router.delete("/messages/{message_id}/reactions/{reaction_type}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_reaction(
    message_id: UUID,
    reaction_type: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove a reaction from a message."""
    msg_repo = MessageRepository(db)
    message = await msg_repo.get_by_id(message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    conv_repo = ConversationRepository(db)
    conversation = await conv_repo.get_by_id(message.conversation_id)
    if not conversation or conversation.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    await db.execute(
        delete(MessageReaction).where(
            MessageReaction.message_id == message_id,
            MessageReaction.user_id == user_id,
            MessageReaction.reaction_type == reaction_type,
        )
    )
    await db.commit()
