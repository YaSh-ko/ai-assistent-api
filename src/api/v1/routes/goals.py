"""
Goal endpoints.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user_id
from src.core.database import get_db
from src.data.repositories.goal import GoalRepository
from src.infrastructure.neo4j_client import neo4j_client
from src.services.entity_serializers import goal_to_response
from src.services.goal_service import create_goal_and_sync
from src.api.v1.schemas.goals import (
    GoalResponse,
    GoalListResponse,
    GoalCreateRequest,
    GoalPatchRequest,
    RelatedEntryResponse,
    ConceptResponse,
)

router = APIRouter()

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

    updated = await repo.update(gid, **update_kwargs)
    return goal_to_response(updated)


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
