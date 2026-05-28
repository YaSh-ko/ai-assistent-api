"""
Goal endpoints.
"""
import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings

from src.api.v1.deps import get_current_user_id
from src.core.database import get_db
from src.data.repositories.goal import GoalRepository
from src.infrastructure.neo4j_client import neo4j_client
from src.services.entity_serializers import goal_to_response
from src.services.goal_service import (
    create_goal_and_sync,
    delete_goal_and_sync,
    sync_goal_to_neo4j,
)
from src.api.v1.schemas.goals import (
    GoalResponse,
    GoalListResponse,
    GoalCreateRequest,
    GoalPatchRequest,
    RelatedEntryResponse,
    ConceptResponse,
)
from src.api.v1.schemas.goal_tasks import (
    GoalTaskCreateRequest,
    GoalTaskListResponse,
    GoalTaskResponse,
    GoalTaskSuggestResponse,
    GoalTaskSuggestedItem,
    GoalTaskUpdateRequest,
    GoalsProgressResponse,
    GoalProgressItem,
)
from src.services.goal_task_serializers import experiment_to_goal_task
from src.services.goal_task_service import (
    create_goal_task,
    delete_goal_task,
    get_goals_task_progress,
    list_goal_tasks,
    update_goal_task,
)

router = APIRouter()
logger = logging.getLogger(__name__)

MSG_GOAL_NOT_FOUND = "Goal not found"


async def _get_goal_response(
    goal_id: str,
    user_id: str,
    db: AsyncSession,
) -> GoalResponse:
    """Load goal from PostgreSQL, fallback to legacy Neo4j-only nodes."""
    try:
        gid = UUID(goal_id)
        repo = GoalRepository(db)
        row = await repo.get_by_id(gid)
        if row and row.user_id == user_id:
            return goal_to_response(row)
    except ValueError:
        pass

    node = await neo4j_client.get_node_by_id(goal_id, "Goal")
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_GOAL_NOT_FOUND,
        )
    if node.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    return GoalResponse(**node)


@router.get("", response_model=GoalListResponse)
async def get_goals(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
):
    """List goals from PostgreSQL."""
    repo = GoalRepository(db)
    rows = await repo.get_by_user_id(user_id, skip=skip, limit=limit)
    return GoalListResponse(goals=[goal_to_response(g) for g in rows])


@router.get("/progress", response_model=GoalsProgressResponse)
async def get_goals_progress(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Task completion progress per goal for the current user."""
    repo = GoalRepository(db)
    rows = await repo.get_by_user_id(user_id, skip=0, limit=500)
    goal_ids = [g.id for g in rows]
    progress_map = await get_goals_task_progress(db, user_id, goal_ids)
    items = [
        GoalProgressItem(
            goal_id=gid,
            total=data["total"],
            completed=data["completed"],
            percent=data["percent"],
        )
        for gid, data in progress_map.items()
    ]
    return GoalsProgressResponse(items=items)


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    request: GoalCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create goal in PostgreSQL and sync to Neo4j."""
    created = await create_goal_and_sync(
        db=db,
        user_id=user_id,
        title=request.title or "",
        description=request.description,
        status=request.status,
        priority=request.priority,
        target_date=request.target_date,
    )
    return goal_to_response(created)


@router.get("/{id}", response_model=GoalResponse)
async def get_goal(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get goal by ID."""
    return await _get_goal_response(id, user_id, db)


@router.patch("/{id}", response_model=GoalResponse)
async def patch_goal(
    id: str,
    request: GoalPatchRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Partially update a goal."""
    try:
        gid = UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid goal ID")

    repo = GoalRepository(db)
    goal = await repo.get_by_id(gid)
    if not goal or goal.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_GOAL_NOT_FOUND)

    update_kwargs = request.model_dump(exclude_none=True)
    if not update_kwargs:
        return goal_to_response(goal)

    new_status = update_kwargs.get("status")
    if new_status == "completed" and goal.status != "completed":
        update_kwargs.setdefault(
            "achieved_at", datetime.now(timezone.utc).replace(tzinfo=None)
        )
    elif new_status in ("active", "paused") and goal.status == "completed":
        update_kwargs["achieved_at"] = None

    updated = await repo.update(gid, **update_kwargs)
    await sync_goal_to_neo4j(updated)
    return goal_to_response(updated)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete goal from PostgreSQL and Neo4j."""
    deleted = await delete_goal_and_sync(db, id, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_GOAL_NOT_FOUND)


@router.get("/{id}/tasks", response_model=GoalTaskListResponse)
async def list_tasks_for_goal(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_goal_response(id, user_id, db)
    gid = UUID(id)
    rows = await list_goal_tasks(db, gid, user_id)
    return GoalTaskListResponse(tasks=[experiment_to_goal_task(r) for r in rows])


@router.post("/{id}/tasks", response_model=GoalTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task_for_goal(
    id: str,
    request: GoalTaskCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_goal_response(id, user_id, db)
    gid = UUID(id)
    created = await create_goal_task(
        db=db,
        user_id=user_id,
        goal_id=gid,
        title=request.title.strip(),
        description=(request.description or request.title).strip(),
        phase=request.phase,
        due_date=request.due_date,
        source=request.source or "user",
    )
    return experiment_to_goal_task(created)


@router.post("/{id}/tasks/suggest", response_model=GoalTaskSuggestResponse)
async def suggest_tasks_for_goal(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """AI-suggested task steps for a goal (proxy to AI service)."""
    goal = await _get_goal_response(id, user_id, db)
    gid = UUID(id)
    existing_rows = await list_goal_tasks(db, gid, user_id)
    existing_dtos = [experiment_to_goal_task(r) for r in existing_rows]
    payload = {
        "title": goal.title,
        "description": goal.description or "",
        "priority": goal.priority,
        "target_date": goal.target_date.isoformat() if goal.target_date else None,
        "existing_tasks": [
            {"title": t.title, "status": t.status, "phase": t.phase or ""}
            for t in existing_dtos
        ],
    }
    url = f"{settings.AI_SERVICE_URL}/api/v1/ai/suggest-goal-tasks"
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            tasks = [
                GoalTaskSuggestedItem(**item)
                for item in data.get("tasks", [])
            ]
            return GoalTaskSuggestResponse(tasks=tasks)
    except Exception as e:
        logger.warning("[Goals] AI task suggest failed for %s: %s", id, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось сгенерировать шаги. Попробуйте позже.",
        )


@router.patch("/{id}/tasks/{task_id}", response_model=GoalTaskResponse)
async def update_task_for_goal(
    id: str,
    task_id: str,
    request: GoalTaskUpdateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_goal_response(id, user_id, db)
    try:
        gid, tid = UUID(id), UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")
    updated = await update_goal_task(
        db, gid, tid, user_id,
        title=request.title.strip() if request.title is not None else None,
        status=request.status,
        phase=request.phase,
        due_date=request.due_date,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return experiment_to_goal_task(updated)


@router.delete("/{id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_for_goal(
    id: str,
    task_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _get_goal_response(id, user_id, db)
    try:
        gid, tid = UUID(id), UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")
    if not await delete_goal_task(db, gid, tid, user_id):
        raise HTTPException(status_code=404, detail="Task not found")


@router.get("/{id}/related-entries", response_model=list[RelatedEntryResponse])
async def get_goal_related_entries(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get entries related to a goal (Neo4j graph)."""
    await _get_goal_response(id, user_id, db)
    entries = await neo4j_client.get_related_nodes(id, "RELATES_TO", "Entry")
    return [RelatedEntryResponse(**entry) for entry in entries]


@router.get("/{id}/concepts", response_model=list[ConceptResponse])
async def get_goal_concepts(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get concepts that a goal is based on (Neo4j graph)."""
    await _get_goal_response(id, user_id, db)
    concepts = await neo4j_client.get_related_nodes(id, "BASED_ON", "Concept")
    return [ConceptResponse(**concept) for concept in concepts]
