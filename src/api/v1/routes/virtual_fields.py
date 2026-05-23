"""
Virtual fields endpoints.
"""
import json
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.v1.deps import get_current_user_id
from src.api.v1.schemas.virtual_fields import (
    SaveVirtualFieldsBoardRequest,
    VirtualFieldsBoardPayload,
    VirtualFieldsBoardResponse,
    VirtualFieldsHistoryResponse,
    VirtualFieldsHistoryItem,
    VirtualFieldsRollbackRequest,
)
from src.infrastructure.neo4j_client import neo4j_client

router = APIRouter()


@router.get("/board/{board_id}", response_model=VirtualFieldsBoardResponse)
async def get_virtual_fields_board(
    board_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get virtual fields board for user."""
    query = """
    MATCH (b:VirtualFieldBoard {user_id: $user_id, board_id: $board_id})
    RETURN b.payload as payload
    LIMIT 1
    """
    result = await neo4j_client.execute_query_async(query, {"user_id": user_id, "board_id": board_id})
    if not result:
        return VirtualFieldsBoardResponse(
            board_id=board_id,
            payload=VirtualFieldsBoardPayload(nodes=[], branchInputs={}),
        )

    raw_payload = result[0].get("payload")
    try:
        payload_data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    except Exception:
        payload_data = {"nodes": [], "branchInputs": {}}

    return VirtualFieldsBoardResponse(
        board_id=board_id,
        payload=VirtualFieldsBoardPayload(**(payload_data or {"nodes": [], "branchInputs": {}})),
    )


@router.put("/board", response_model=VirtualFieldsBoardResponse)
async def save_virtual_fields_board(
    request: SaveVirtualFieldsBoardRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Save virtual fields board for user."""
    query = """
    MERGE (b:VirtualFieldBoard {user_id: $user_id, board_id: $board_id})
    SET b.payload = $payload,
        b.updated_at = datetime(),
        b.created_at = coalesce(b.created_at, datetime())
    RETURN b.board_id as board_id, b.payload as payload
    """
    history_query = """
    MATCH (b:VirtualFieldBoard {user_id: $user_id, board_id: $board_id})
    CREATE (h:VirtualFieldBoardVersion {
      version_id: $version_id,
      board_id: $board_id,
      user_id: $user_id,
      payload: $payload,
      changed_by: $user_id,
      changed_at: datetime()
    })
    MERGE (h)-[:VERSION_OF]->(b)
    RETURN h.version_id as version_id
    """

    try:
        result = await neo4j_client.execute_query_async(
            query,
            {
                "user_id": user_id,
                "board_id": request.board_id,
                "payload": request.payload.model_dump_json(),
            },
        )
        await neo4j_client.execute_query_async(
            history_query,
            {
                "user_id": user_id,
                "board_id": request.board_id,
                "payload": request.payload.model_dump_json(),
                "version_id": str(uuid4()),
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save virtual fields board: {str(e)}",
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Board was not saved",
        )

    raw_payload = result[0].get("payload")
    payload_data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    return VirtualFieldsBoardResponse(
        board_id=result[0]["board_id"],
        payload=VirtualFieldsBoardPayload(**payload_data),
    )


@router.get("/board/{board_id}/history", response_model=VirtualFieldsHistoryResponse)
async def get_virtual_fields_history(
    board_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get board version history."""
    query = """
    MATCH (h:VirtualFieldBoardVersion {user_id: $user_id, board_id: $board_id})
    RETURN h.version_id as version_id, h.board_id as board_id, h.changed_by as changed_by, h.changed_at as changed_at
    ORDER BY h.changed_at DESC
    LIMIT 30
    """
    rows = await neo4j_client.execute_query_async(query, {"user_id": user_id, "board_id": board_id})
    items = [
        VirtualFieldsHistoryItem(
            version_id=str(row.get("version_id", "")),
            board_id=str(row.get("board_id", board_id)),
            changed_by=str(row.get("changed_by", user_id)),
            changed_at=str(row.get("changed_at", "")),
        )
        for row in rows
    ]
    return VirtualFieldsHistoryResponse(items=items)


@router.post("/board/rollback", response_model=VirtualFieldsBoardResponse)
async def rollback_virtual_fields_board(
    request: VirtualFieldsRollbackRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Rollback board to a specific version."""
    query = """
    MATCH (h:VirtualFieldBoardVersion {user_id: $user_id, board_id: $board_id, version_id: $version_id})
    WITH h
    MATCH (b:VirtualFieldBoard {user_id: $user_id, board_id: $board_id})
    SET b.payload = h.payload,
        b.updated_at = datetime()
    RETURN b.board_id as board_id, b.payload as payload
    """
    rows = await neo4j_client.execute_query_async(
        query,
        {
            "user_id": user_id,
            "board_id": request.board_id,
            "version_id": request.version_id,
        },
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found for rollback",
        )
    raw_payload = rows[0].get("payload")
    payload_data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    return VirtualFieldsBoardResponse(
        board_id=rows[0]["board_id"],
        payload=VirtualFieldsBoardPayload(**payload_data),
    )
