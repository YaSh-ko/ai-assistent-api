"""
Schemas for graph endpoints.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class GraphNode(BaseModel):
    """Node in the graph."""
    id: str
    user: str
    description: str
    type: str
    # Additional properties can be added dynamically
    model_config = {"extra": "allow"}


class GraphLink(BaseModel):
    """Link/edge in the graph."""
    source: str
    target: str
    type: Optional[str] = None
    reason: Optional[str] = None
    model_config = {"extra": "allow"}


class RhizomeGraphResponse(BaseModel):
    """Response for rhizome graph endpoint."""
    nodes: List[GraphNode]
    links: List[GraphLink]


class GraphSearchResponse(BaseModel):
    """Response for graph search endpoint."""
    nodes: List[GraphNode]


class RelationshipProperties(BaseModel):
    """Properties for a graph relationship."""
    model_config = {"extra": "allow"}


class RelationshipCreateRequest(BaseModel):
    """Request to create a relationship between two nodes in Neo4j."""
    from_type: str          # e.g. "Entry"
    from_id: str
    to_type: str            # e.g. "Concept"
    to_id: str
    relationship: str       # e.g. "MENTIONS" | "EVOLVESINTO"
    properties: Dict[str, Any] = {}


class RelationshipResponse(BaseModel):
    """Response after creating a relationship."""
    from_id: str
    to_id: str
    relationship: str
    properties: Dict[str, Any] = {}


class RelationshipDeleteRequest(BaseModel):
    """Request to delete a relationship between two nodes in Neo4j."""
    from_id: str
    to_id: str
    relationship: str


class RelationshipDeleteResponse(BaseModel):
    """Response after deleting relationship(s)."""
    from_id: str
    to_id: str
    relationship: str
    deleted_count: int


class GraphNodeUpdateRequest(BaseModel):
    """Request to update graph node properties."""
    description: Optional[str] = None
    image_url: Optional[str] = None
    title: Optional[str] = None


class GraphNodeUpdateResponse(BaseModel):
    """Response after updating graph node properties."""
    id: str
    type: str
    properties: Dict[str, Any]


class RelationshipHistoryItem(BaseModel):
    """Audit item for relationship change."""
    audit_id: str
    from_id: str
    to_id: str
    relationship: str
    action: str
    changed_by: str
    changed_at: str


class RelationshipHistoryResponse(BaseModel):
    """History list response."""
    items: List[RelationshipHistoryItem]


class RelationshipRollbackRequest(BaseModel):
    """Rollback relationship change request."""
    audit_id: str
