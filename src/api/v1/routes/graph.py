"""
Graph endpoints for rhizome visualization.
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Annotated, List, Optional, cast
from typing import LiteralString
import logging
from uuid import uuid4

from src.api.v1.deps import get_current_user_id
from src.infrastructure.neo4j_client import neo4j_client
from src.api.v1.schemas.graph import (
    RhizomeGraphResponse,
    GraphSearchResponse,
    GraphNode,
    RelationshipCreateRequest,
    RelationshipResponse,
    RelationshipDeleteRequest,
    RelationshipDeleteResponse,
    GraphNodeUpdateRequest,
    GraphNodeUpdateResponse,
    RelationshipHistoryResponse,
    RelationshipHistoryItem,
    RelationshipRollbackRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/rhizome", response_model=RhizomeGraphResponse)
async def get_rhizome_graph(
    user_id: Annotated[str, Depends(get_current_user_id)],
    node_types: Annotated[Optional[List[str]], Query(description="Filter by node types")] = None,
    time_period: Annotated[Optional[str], Query(description="Filter by time period: past, present, future")] = None,
):
    """
    Get the complete graph for a user.
    
    Returns nodes and links in format suitable for react-force-graph.
    """
    try:
        graph_data = await neo4j_client.get_rhizome_graph(
            user_id=user_id,
            node_types=node_types,
            time_period=time_period
        )
        return RhizomeGraphResponse(**graph_data)
    except Exception as e:
        error_msg = str(e)
        logger.error("get_rhizome_graph failed for user=%s: %s", user_id, error_msg, exc_info=True)
        # Если Neo4j недоступен — возвращаем пустой граф, страница всё равно рендерится
        lower = error_msg.lower()
        if any(k in lower for k in ("connection", "refused", "unavailable", "timeout", "ssl", "auth")):
            return RhizomeGraphResponse(nodes=[], links=[])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch graph: {error_msg}",
        )


@router.get("/search", response_model=GraphSearchResponse)
async def search_graph_nodes(
    user_id: Annotated[str, Depends(get_current_user_id)],
    query: Annotated[str, Query(description="Search query")],
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of results")] = 50,
):
    """
    Search nodes by name or title.
    """
    try:
        nodes = await neo4j_client.search_nodes(user_id=user_id, query=query, limit=limit)
        return GraphSearchResponse(nodes=[GraphNode(**node) for node in nodes])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search nodes: {str(e)}"
        )


# Allowed relationship types to prevent Cypher injection
_ALLOWED_RELATIONSHIPS = {"MENTIONS", "EVOLVESINTO", "RELATED", "DOCUMENTS", "INFLUENCES"}
_ALLOWED_NODE_TYPES = {"Entry", "Goal", "Experiment", "Concept", "Analysis", "Topic"}


@router.post("/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    request: RelationshipCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Create a relationship between two Neo4j nodes (e.g. Entry -[:MENTIONS]-> Concept)."""
    if request.relationship not in _ALLOWED_RELATIONSHIPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Relationship type '{request.relationship}' is not allowed.",
        )

    query = cast(LiteralString, f"""
    MATCH (a:{request.from_type} {{id: $from_id}})
    MATCH (b:{request.to_type} {{id: $to_id}})
    MERGE (a)-[r:{request.relationship}]->(b)
    SET r += $props
    RETURN r
    """)

    try:
        await neo4j_client.execute_query_async(query, {
            "from_id": request.from_id,
            "to_id": request.to_id,
            "props": request.properties,
        })
        await neo4j_client.execute_query_async(
            """
            CREATE (a:RelationshipAudit {
              audit_id: $audit_id,
              from_id: $from_id,
              to_id: $to_id,
              relationship: $relationship,
              action: 'create',
              changed_by: $user_id,
              changed_at: datetime()
            })
            """,
            {
                "audit_id": str(uuid4()),
                "from_id": request.from_id,
                "to_id": request.to_id,
                "relationship": request.relationship,
                "user_id": user_id,
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create relationship: {str(e)}",
        )

    return RelationshipResponse(
        from_id=request.from_id,
        to_id=request.to_id,
        relationship=request.relationship,
        properties=request.properties,
    )


@router.delete("/relationships", response_model=RelationshipDeleteResponse)
async def delete_relationship(
    request: RelationshipDeleteRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Delete a relationship between two user-owned nodes."""
    if request.relationship not in _ALLOWED_RELATIONSHIPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Relationship type '{request.relationship}' is not allowed.",
        )

    query = cast(LiteralString, f"""
    MATCH (a {{id: $from_id, user_id: $user_id}})-[r:{request.relationship}]->(b {{id: $to_id, user_id: $user_id}})
    WITH collect(r) as rels
    FOREACH (rel IN rels | DELETE rel)
    RETURN size(rels) as deleted_count
    """)

    try:
        result = await neo4j_client.execute_query_async(query, {
            "from_id": request.from_id,
            "to_id": request.to_id,
            "user_id": user_id,
        })
        deleted_count = int(result[0].get("deleted_count", 0)) if result else 0
        if deleted_count > 0:
            await neo4j_client.execute_query_async(
                """
                CREATE (a:RelationshipAudit {
                  audit_id: $audit_id,
                  from_id: $from_id,
                  to_id: $to_id,
                  relationship: $relationship,
                  action: 'delete',
                  changed_by: $user_id,
                  changed_at: datetime()
                })
                """,
                {
                    "audit_id": str(uuid4()),
                    "from_id": request.from_id,
                    "to_id": request.to_id,
                    "relationship": request.relationship,
                    "user_id": user_id,
                },
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete relationship: {str(e)}",
        )

    return RelationshipDeleteResponse(
        from_id=request.from_id,
        to_id=request.to_id,
        relationship=request.relationship,
        deleted_count=deleted_count,
    )


@router.patch("/nodes/{node_type}/{node_id}", response_model=GraphNodeUpdateResponse)
async def update_graph_node(
    node_type: str,
    node_id: str,
    request: GraphNodeUpdateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Update editable node properties directly from graph UI."""
    if node_type not in _ALLOWED_NODE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Node type '{node_type}' is not allowed.",
        )

    payload = request.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update.",
        )

    query = cast(LiteralString, f"""
    MATCH (n:{node_type} {{id: $node_id, user_id: $user_id}})
    SET n += $payload,
        n.updated_at = datetime()
    RETURN n
    """)
    result = await neo4j_client.execute_query_async(
        query,
        {"node_id": node_id, "user_id": user_id, "payload": payload},
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
    node = dict(result[0]["n"])
    return GraphNodeUpdateResponse(id=node_id, type=node_type, properties=node)


@router.get("/relationships/history", response_model=RelationshipHistoryResponse)
async def get_relationship_history(
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get relationship change history."""
    rows = await neo4j_client.execute_query_async(
        """
        MATCH (a:RelationshipAudit {changed_by: $user_id})
        RETURN a.audit_id as audit_id,
               a.from_id as from_id,
               a.to_id as to_id,
               a.relationship as relationship,
               a.action as action,
               a.changed_by as changed_by,
               a.changed_at as changed_at
        ORDER BY a.changed_at DESC
        LIMIT 50
        """,
        {"user_id": user_id},
    )
    items = [
        RelationshipHistoryItem(
            audit_id=str(row.get("audit_id", "")),
            from_id=str(row.get("from_id", "")),
            to_id=str(row.get("to_id", "")),
            relationship=str(row.get("relationship", "")),
            action=str(row.get("action", "")),
            changed_by=str(row.get("changed_by", user_id)),
            changed_at=str(row.get("changed_at", "")),
        )
        for row in rows
    ]
    return RelationshipHistoryResponse(items=items)


@router.post("/relationships/rollback", response_model=RelationshipResponse)
async def rollback_relationship(
    request: RelationshipRollbackRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Rollback single relationship audit action."""
    rows = await neo4j_client.execute_query_async(
        """
        MATCH (a:RelationshipAudit {audit_id: $audit_id, changed_by: $user_id})
        RETURN a.from_id as from_id,
               a.to_id as to_id,
               a.relationship as relationship,
               a.action as action
        LIMIT 1
        """,
        {"audit_id": request.audit_id, "user_id": user_id},
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit item not found")
    row = rows[0]
    from_id = str(row.get("from_id", ""))
    to_id = str(row.get("to_id", ""))
    relationship = str(row.get("relationship", ""))
    action = str(row.get("action", ""))

    if relationship not in _ALLOWED_RELATIONSHIPS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Relationship type is not allowed")

    if action == "delete":
        await neo4j_client.execute_query_async(
            cast(LiteralString, f"""
            MATCH (a {{id: $from_id, user_id: $user_id}})
            MATCH (b {{id: $to_id, user_id: $user_id}})
            MERGE (a)-[r:{relationship}]->(b)
            RETURN r
            """),
            {"from_id": from_id, "to_id": to_id, "user_id": user_id},
        )
    elif action == "create":
        await neo4j_client.execute_query_async(
            cast(LiteralString, f"""
            MATCH (a {{id: $from_id, user_id: $user_id}})-[r:{relationship}]->(b {{id: $to_id, user_id: $user_id}})
            DELETE r
            """),
            {"from_id": from_id, "to_id": to_id, "user_id": user_id},
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported audit action")

    return RelationshipResponse(
        from_id=from_id,
        to_id=to_id,
        relationship=relationship,
        properties={"rollback_from_audit": request.audit_id, "rolled_back_action": action},
    )
