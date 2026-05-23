"""
Schemas for concept endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ConceptCreateRequest(BaseModel):
    """Request to create a Concept node in Neo4j."""
    name: str
    description: Optional[str] = None
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    source_entry_id: Optional[str] = None
    source_thread_id: Optional[str] = None


class ConceptResponse(BaseModel):
    """Response after creating or fetching a Concept."""
    id: str
    name: str
    description: Optional[str] = None
    relevance: float
    user_id: str
    created_at: Optional[datetime] = None
