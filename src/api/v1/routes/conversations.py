"""
Conversation endpoints.
"""
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select
from common.database.models import Entry, EntryThread
from src.api.v1.deps import get_current_user_id
from src.core.database import get_db
from src.data.repositories.conversation import ConversationRepository
from src.api.v1.schemas.conversations import (
    ConversationResponse,
    ConversationListResponse,
    ThreadContextResponse,
    CreateCategoryConversationRequest,
    CategoryConversationResponse,
    UpdateThreadCategoryRequest,
)

router = APIRouter()

_ERR_NOT_FOUND = "Conversation not found"
_ERR_ACCESS_DENIED = "Access denied"


@router.get("", response_model=ConversationListResponse)
async def get_conversations(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
):
    """Get list of conversations."""
    repo = ConversationRepository(db)
    conversations = await repo.get_by_user_id(user_id, skip=skip, limit=limit)
    return ConversationListResponse(
        conversations=[ConversationResponse.model_validate(c) for c in conversations]
    )


@router.get("/recent", response_model=ConversationListResponse)
async def get_recent_conversations(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
):
    """Get recent conversations."""
    repo = ConversationRepository(db)
    conversations = await repo.get_recent(user_id, limit=limit)
    return ConversationListResponse(
        conversations=[ConversationResponse.model_validate(c) for c in conversations]
    )


@router.post("/category", response_model=CategoryConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_category_conversation(
    request: CreateCategoryConversationRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new conversation pre-assigned to a category."""
    repo = ConversationRepository(db)
    thread_id = str(uuid4())
    conversation = await repo.create_with_metadata(
        user_id=user_id,
        thread_id=thread_id,
        meta_data={"category": request.category},
        title="Новый чат",
    )
    return CategoryConversationResponse(
        thread_id=conversation.thread_id,
        conversation_id=str(conversation.id),
    )


@router.get("/{id}", response_model=ConversationResponse)
async def get_conversation(
    id: UUID,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get conversation by ID."""
    repo = ConversationRepository(db)
    conversation = await repo.get_by_id(id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_ERR_NOT_FOUND
        )
    if conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_ERR_ACCESS_DENIED
        )
    return ConversationResponse.model_validate(conversation)


@router.patch("/thread/{thread_id}/title")
async def update_thread_title(
    thread_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: dict,
):
    """Update conversation title by thread_id."""
    repo = ConversationRepository(db)
    conversation = await repo.get_by_thread_id(thread_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_ERR_NOT_FOUND)
    if conversation.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ERR_ACCESS_DENIED)
    title = body.get("title", "")
    await repo.update(conversation.id, title=title)
    return {"thread_id": thread_id, "title": title}


@router.patch("/thread/{thread_id}/category")
async def update_thread_category(
    thread_id: str,
    request: UpdateThreadCategoryRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update conversation category by thread_id."""
    repo = ConversationRepository(db)
    conversation = await repo.get_by_thread_id(thread_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_ERR_NOT_FOUND)
    if conversation.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ERR_ACCESS_DENIED)
    meta = dict(conversation.meta_data or {})
    meta["category"] = request.category
    await repo.update(conversation.id, meta_data=meta)
    return {"thread_id": thread_id, "category": request.category}


@router.get("/thread/{thread_id}/context", response_model=ThreadContextResponse)
async def get_thread_context(
    thread_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get context for a conversation thread (e.g., related Entry)."""
    stmt = select(EntryThread).where(
        EntryThread.thread_id == thread_id,
        EntryThread.user_id == user_id
    )
    result = await db.execute(stmt)
    entry_thread = result.scalar_one_or_none()
    
    if not entry_thread:
        return ThreadContextResponse(
            type="general",
            title="Свободный диалог",
            description="Ни к чему не привязанный чатик",
            entry_id=None
        )
        
    stmt_entry = select(Entry).where(Entry.id == entry_thread.entry_id)
    entry_result = await db.execute(stmt_entry)
    entry = entry_result.scalar_one_or_none()
    
    if not entry:
        return ThreadContextResponse(
            type="general",
            title="Свободный диалог",
            description="Ни к чему не привязанный чатик",
            entry_id=None
        )
        
    # Форматируем короткое описание
    desc = entry.description or ""
    if len(desc) > 100:
        desc = desc[:100] + "..."
        
    return ThreadContextResponse(
        type="event",
        title=entry.title or "Событие",
        description=desc,
        entry_id=entry.id
    )
