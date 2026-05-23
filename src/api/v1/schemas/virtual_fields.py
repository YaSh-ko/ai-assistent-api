"""
Schemas for virtual fields endpoints.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Literal, Optional


class VirtualFieldNode(BaseModel):
    """Canvas node for virtual fields board."""
    id: str
    parentId: Optional[str] = None
    type: Literal["question", "answer"]
    text: str
    x: float
    y: float


class VirtualFieldsBoardPayload(BaseModel):
    """Payload saved for a user board."""
    nodes: List[VirtualFieldNode]
    branchInputs: Dict[str, str]


class SaveVirtualFieldsBoardRequest(BaseModel):
    """Save board request."""
    board_id: str = Field(min_length=1)
    payload: VirtualFieldsBoardPayload


class VirtualFieldsBoardResponse(BaseModel):
    """Board response."""
    board_id: str
    payload: VirtualFieldsBoardPayload


class VirtualFieldsHistoryItem(BaseModel):
    """Version history item for board."""
    version_id: str
    board_id: str
    changed_by: str
    changed_at: str


class VirtualFieldsHistoryResponse(BaseModel):
    """History response."""
    items: List[VirtualFieldsHistoryItem]


class VirtualFieldsRollbackRequest(BaseModel):
    """Rollback request."""
    board_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
