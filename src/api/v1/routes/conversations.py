"""
Conversation endpoints.
"""
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, delete
from common.database.models import (
    Entry,
    Goal,
    Experiment,
    EntryThread,
    GoalThread,
    ExperimentThread,
    AnalysisThread,
)
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
    LinkThreadRequest,
    LinkThreadResponse,
    EntityThreadsResponse,
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


@router.delete("/thread/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete conversation and thread links for the current user."""
    repo = ConversationRepository(db)
    conversation = await repo.get_by_thread_id(thread_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_ERR_NOT_FOUND)
    if conversation.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ERR_ACCESS_DENIED)

    for model in (EntryThread, GoalThread, ExperimentThread, AnalysisThread):
        await db.execute(
            delete(model).where(
                model.thread_id == thread_id,
                model.user_id == user_id,
            )
        )

    deleted = await repo.delete(conversation.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_ERR_NOT_FOUND)


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


@router.get("/entity/{entity_type}/{entity_id}/threads", response_model=EntityThreadsResponse)
async def get_entity_threads(
    entity_type: str,
    entity_id: UUID,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get thread_ids linked to an entity."""
    if entity_type == "observation":
        stmt = select(EntryThread.thread_id).where(
            EntryThread.entry_id == entity_id, EntryThread.user_id == user_id
        )
    elif entity_type == "goal":
        stmt = select(GoalThread.thread_id).where(
            GoalThread.goal_id == entity_id, GoalThread.user_id == user_id
        )
    elif entity_type == "task":
        stmt = select(ExperimentThread.thread_id).where(
            ExperimentThread.experiment_id == entity_id, ExperimentThread.user_id == user_id
        )
    else:
        raise HTTPException(status_code=400, detail="Unknown entity_type")

    rows = (await db.execute(stmt)).scalars().all()
    return EntityThreadsResponse(
        entity_type=entity_type,
        entity_id=entity_id,
        thread_ids=list(rows),
    )


@router.post("/thread/{thread_id}/link", response_model=LinkThreadResponse, status_code=status.HTTP_201_CREATED)
async def link_thread_to_entity(
    thread_id: str,
    request: LinkThreadRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Link a thread to an entity (observation, goal, or task)."""
    eid = request.entity_id

    if request.entity_type == "observation":
        link = EntryThread(user_id=user_id, entry_id=eid, thread_id=thread_id)
    elif request.entity_type == "goal":
        link = GoalThread(user_id=user_id, goal_id=eid, thread_id=thread_id)
    elif request.entity_type == "task":
        link = ExperimentThread(user_id=user_id, experiment_id=eid, thread_id=thread_id)
    else:
        raise HTTPException(status_code=400, detail="Unknown entity_type")

    db.add(link)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Link already exists")

    return LinkThreadResponse(
        thread_id=thread_id,
        entity_type=request.entity_type,
        entity_id=eid,
    )


def _short_desc(text: str | None, max_len: int = 100) -> str:
    if not text:
        return ""
    return text[:max_len] + "..." if len(text) > max_len else text


@router.get("/thread/{thread_id}/context", response_model=ThreadContextResponse)
async def get_thread_context(
    thread_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get context for a conversation thread — checks entries, goals, experiments."""
    _general = ThreadContextResponse(
        type="general",
        title="Свободный диалог",
        description="",
    )

    # 1. Check entry link
    row = (await db.execute(
        select(EntryThread).where(EntryThread.thread_id == thread_id, EntryThread.user_id == user_id)
    )).scalar_one_or_none()
    if row:
        entry = (await db.execute(select(Entry).where(Entry.id == row.entry_id))).scalar_one_or_none()
        if entry:
            return ThreadContextResponse(
                type="observation",
                title=entry.title or "Наблюдение",
                description=_short_desc(entry.description),
                entity_id=entry.id,
                entry_id=entry.id,
            )

    # 2. Check goal link
    row = (await db.execute(
        select(GoalThread).where(GoalThread.thread_id == thread_id, GoalThread.user_id == user_id)
    )).scalar_one_or_none()
    if row:
        goal = (await db.execute(select(Goal).where(Goal.id == row.goal_id))).scalar_one_or_none()
        if goal:
            return ThreadContextResponse(
                type="goal",
                title=goal.title or "Цель",
                description=_short_desc(goal.description),
                entity_id=goal.id,
            )

    # 3. Check experiment/task link
    row = (await db.execute(
        select(ExperimentThread).where(ExperimentThread.thread_id == thread_id, ExperimentThread.user_id == user_id)
    )).scalar_one_or_none()
    if row:
        exp = (await db.execute(select(Experiment).where(Experiment.id == row.experiment_id))).scalar_one_or_none()
        if exp:
            return ThreadContextResponse(
                type="task",
                title=exp.title or "Задача",
                description=_short_desc(exp.description),
                entity_id=exp.id,
            )

    return _general
