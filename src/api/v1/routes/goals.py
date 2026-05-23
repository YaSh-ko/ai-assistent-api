"""
Goal endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user_id
from src.core.database import get_db
from src.infrastructure.neo4j_client import neo4j_client
from src.api.v1.schemas.goals import (
    GoalResponse,
    GoalListResponse,
    RelatedEntryResponse,
    ConceptResponse,
)

router = APIRouter()

MSG_GOAL_NOT_FOUND = "Goal not found"


@router.get("", response_model=GoalListResponse)
async def get_goals(
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get list of goals from Neo4j."""
    query = """
    MATCH (g:Goal {user_id: $user_id})
    RETURN g
    ORDER BY g.created_at DESC
    """
    results = await neo4j_client.execute_query_async(query, {"user_id": user_id})
    goals = [GoalResponse(**record["g"]) for record in results]
    return GoalListResponse(goals=goals)


@router.get("/{id}", response_model=GoalResponse)
async def get_goal(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get goal by ID from Neo4j."""
    goal = await neo4j_client.get_node_by_id(id, "Goal")
    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_GOAL_NOT_FOUND
        )
    if goal.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    return GoalResponse(**goal)


@router.get("/{id}/related-entries", response_model=list[RelatedEntryResponse])
async def get_goal_related_entries(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get entries related to a goal."""
    # Verify goal exists
    goal = await neo4j_client.get_node_by_id(id, "Goal")
    if not goal or goal.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_GOAL_NOT_FOUND
        )
    
    entries = await neo4j_client.get_related_nodes(id, "RELATES_TO", "Entry")
    return [RelatedEntryResponse(**entry) for entry in entries]


@router.get("/{id}/concepts", response_model=list[ConceptResponse])
async def get_goal_concepts(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get concepts that a goal is based on."""
    # Verify goal exists
    goal = await neo4j_client.get_node_by_id(id, "Goal")
    if not goal or goal.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_GOAL_NOT_FOUND
        )
    
    concepts = await neo4j_client.get_related_nodes(id, "BASED_ON", "Concept")
    return [ConceptResponse(**concept) for concept in concepts]
