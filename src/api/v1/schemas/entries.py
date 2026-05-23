"""
Schemas for entry endpoints.
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
from uuid import UUID


class EntryResponse(BaseModel):
    """Entry response model."""
    id: UUID
    user_id: str
    title: Optional[str] = None
    description: str
    event_date: date
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class EntryCreateRequest(BaseModel):
    """Request to create an entry."""
    title: Optional[str] = None
    description: str
    event_date: date


class EntryListResponse(BaseModel):
    """List of entries."""
    entries: List[EntryResponse]


class IntensityMetricResponse(BaseModel):
    """Intensity metric response."""
    id: UUID
    user_id: str
    entity_type: str
    entity_id: UUID
    intensity_value: float
    metric_date: date
    note: Optional[str] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class IntensityMetricCreateRequest(BaseModel):
    """Request to create an intensity metric."""
    intensity_value: float
    metric_date: date
    note: Optional[str] = None


class RelatedSituationResponse(BaseModel):
    """Related situation response."""
    id: UUID
    user_id: str
    source_type: str
    source_id: UUID
    target_type: str
    target_id: UUID
    target_title: Optional[str] = None
    relation_type: str
    created_at: datetime
    
    model_config = {"from_attributes": True}


class NegativeImpactResponse(BaseModel):
    """Negative impact response."""
    id: UUID
    user_id: str
    source_type: str
    source_id: UUID
    title: str
    description: Optional[str] = None
    severity: Optional[int] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class TransformationResponse(BaseModel):
    """Transformation response."""
    id: UUID
    user_id: str
    source_type: str
    source_id: UUID
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class EntryAnalysisResponse(BaseModel):
    """Complete analysis response for an entry."""
    entry: EntryResponse
    intensity_metrics: List[IntensityMetricResponse]
    related_situations: List[RelatedSituationResponse]
    negative_impacts: List[NegativeImpactResponse]
    transformations: List[TransformationResponse]
    concepts: List[dict]  # From Neo4j


class EntryPatchRequest(BaseModel):
    """Request to partially update an entry (silent enrichment from chat)."""
    title: Optional[str] = None
    description: Optional[str] = None
    event_date: Optional[date] = None


class NegativeImpactCreateRequest(BaseModel):
    """Request to create a negative impact for an entry."""
    title: str
    description: Optional[str] = None
    severity: Optional[int] = None  # 1–10


class TransformationCreateRequest(BaseModel):
    """Request to create a transformation for an entry."""
    title: str
    description: Optional[str] = None
    category: Optional[str] = None  # behaviorChange | beliefChange | relationshipRule
