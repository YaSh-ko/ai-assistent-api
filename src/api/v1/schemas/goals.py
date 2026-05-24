"""
Schemas for goal endpoints.
"""
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime, date
from uuid import UUID


class GoalResponse(BaseModel):
    """Goal response from Neo4j."""
    id: str
    title: str
    description: Optional[str] = None
    status: str
    priority: Optional[str] = None
    created_at: Optional[datetime] = None
    target_date: Optional[date] = None
    achieved_at: Optional[datetime] = None
    user_id: str
    updated_at: Optional[datetime] = None

    @field_validator('created_at', 'achieved_at', 'updated_at', mode='before')
    @classmethod
    def coerce_neo4j_datetime(cls, v):
        if v is None:
            return None
        # neo4j.time.DateTime → python datetime
        if hasattr(v, 'to_native'):
            return v.to_native()
        return v

    @field_validator('target_date', mode='before')
    @classmethod
    def coerce_neo4j_date(cls, v):
        if v is None:
            return None
        if hasattr(v, 'to_native'):
            native = v.to_native()
            return native.date() if hasattr(native, 'date') else native
        return v

    model_config = {"extra": "allow"}


class GoalCreateRequest(BaseModel):
    """Request to create a goal."""
    title: Optional[str] = None
    description: str
    status: str = "active"
    priority: str = "medium"
    target_date: Optional[date] = None


class GoalListResponse(BaseModel):
    """List of goals."""
    goals: List[GoalResponse]


class RelatedEntryResponse(BaseModel):
    """Entry related to a goal."""
    id: str
    content: str
    content_summary: Optional[str] = None
    timestamp: datetime
    user_id: str
    
    model_config = {"extra": "allow"}


class ConceptResponse(BaseModel):
    """Concept response from Neo4j."""
    id: str
    name: str
    description: Optional[str] = None
    relevance: Optional[float] = None
    user_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def coerce_neo4j_datetime(cls, v):
        if v is None:
            return None
        if hasattr(v, 'to_native'):
            return v.to_native()
        return v

    model_config = {"extra": "allow"}
