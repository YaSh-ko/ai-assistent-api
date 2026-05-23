"""
Schemas for analysis endpoints.
"""
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime


class AnalysisResponse(BaseModel):
    """Analysis response from Neo4j."""
    id: str
    title: str
    content: str
    summary: Optional[str] = None
    analyzed_at: Optional[datetime] = None
    user_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('analyzed_at', 'created_at', 'updated_at', mode='before')
    @classmethod
    def coerce_neo4j_datetime(cls, v):
        if v is None:
            return None
        if hasattr(v, 'to_native'):
            return v.to_native()
        return v

    model_config = {"extra": "allow"}
