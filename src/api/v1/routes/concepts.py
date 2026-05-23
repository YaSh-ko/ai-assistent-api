"""
Concept endpoints — Neo4j Concept nodes.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.v1.deps import get_current_user_id
from src.infrastructure.neo4j_client import neo4j_client
from src.api.v1.schemas.concepts import ConceptCreateRequest, ConceptResponse

router = APIRouter()


@router.post("", response_model=ConceptResponse, status_code=status.HTTP_201_CREATED)
async def create_concept(
    request: ConceptCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Create a Concept node in Neo4j (behavioral insight extracted from chat)."""
    concept_id = str(uuid.uuid4())

    query = """
    CREATE (c:Concept {
        id: $id,
        name: $name,
        description: $description,
        relevance: $relevance,
        user_id: $user_id,
        source_entry_id: $source_entry_id,
        source_thread_id: $source_thread_id,
        created_at: datetime(),
        updated_at: datetime()
    })
    RETURN c
    """
    results = await neo4j_client.execute_query_async(query, {
        "id": concept_id,
        "name": request.name,
        "description": request.description or "",
        "relevance": request.relevance,
        "user_id": user_id,
        "source_entry_id": request.source_entry_id or "",
        "source_thread_id": request.source_thread_id or "",
    })

    if not results:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create concept in Neo4j",
        )

    node = results[0]["c"]
    return ConceptResponse(
        id=concept_id,
        name=node.get("name", request.name),
        description=node.get("description") or None,
        relevance=node.get("relevance", request.relevance),
        user_id=user_id,
        created_at=None,
    )
