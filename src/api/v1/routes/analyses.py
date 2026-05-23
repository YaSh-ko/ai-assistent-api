"""
Analysis endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.deps import get_current_user_id
from src.core.database import get_db
from src.infrastructure.neo4j_client import neo4j_client
from src.api.v1.schemas.analyses import AnalysisResponse
from src.api.v1.schemas.goals import GoalResponse, ConceptResponse
from src.api.v1.schemas.experiments import ExperimentResponse

router = APIRouter()

MSG_ANALYSIS_NOT_FOUND = "Analysis not found"


@router.get("/{id}", response_model=AnalysisResponse)
async def get_analysis(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get analysis by ID from Neo4j."""
    analysis = await neo4j_client.get_node_by_id(id, "Analysis")
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ANALYSIS_NOT_FOUND
        )
    if analysis.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    return AnalysisResponse(**analysis)


@router.get("/{id}/concepts", response_model=list[ConceptResponse])
async def get_analysis_concepts(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get concepts produced by an analysis."""
    # Verify analysis exists
    analysis = await neo4j_client.get_node_by_id(id, "Analysis")
    if not analysis or analysis.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ANALYSIS_NOT_FOUND
        )
    
    concepts = await neo4j_client.get_related_nodes(id, "PRODUCES", "Concept")
    return [ConceptResponse(**concept) for concept in concepts]


@router.get("/{id}/goals", response_model=list[GoalResponse])
async def get_analysis_goals(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get goals that an analysis led to."""
    # Verify analysis exists
    analysis = await neo4j_client.get_node_by_id(id, "Analysis")
    if not analysis or analysis.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ANALYSIS_NOT_FOUND
        )
    
    goals = await neo4j_client.get_related_nodes(id, "LEADS_TO", "Goal")
    return [GoalResponse(**goal) for goal in goals]


@router.get("/{id}/experiments", response_model=list[ExperimentResponse])
async def get_analysis_experiments(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get experiments that an analysis led to."""
    # Verify analysis exists
    analysis = await neo4j_client.get_node_by_id(id, "Analysis")
    if not analysis or analysis.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ANALYSIS_NOT_FOUND
        )
    
    experiments = await neo4j_client.get_related_nodes(id, "LEADS_TO", "Experiment")
    return [ExperimentResponse(**experiment) for experiment in experiments]
