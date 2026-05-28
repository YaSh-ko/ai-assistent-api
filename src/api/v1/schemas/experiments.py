"""
Schemas for experiment endpoints.
"""
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime, date
from uuid import UUID

from src.api.v1.schemas.entries import IntensityMetricResponse


class ExperimentResponse(BaseModel):
    """Experiment response from Neo4j."""
    id: str
    title: str
    description: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    outcome: Optional[str] = None
    success: Optional[int] = None
    user_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('started_at', 'ended_at', 'created_at', 'updated_at', mode='before')
    @classmethod
    def coerce_neo4j_datetime(cls, v):
        if v is None:
            return None
        if hasattr(v, 'to_native'):
            return v.to_native()
        return v

    model_config = {"extra": "allow"}


class ExperimentSummaryResponse(BaseModel):
    """Experiment summary with metrics."""
    experiment: ExperimentResponse
    average_intensity: Optional[float] = None
    intensity_metrics: List[dict]  # From PostgreSQL


class EntryForExperimentResponse(BaseModel):
    """Entry that documents an experiment."""
    id: str
    content: str
    content_summary: Optional[str] = None
    timestamp: datetime
    user_id: str
    
    model_config = {"extra": "allow"}


class RelatedEntryResponse(BaseModel):
    """Запись (Entry), связанная с экспериментом через DOCUMENTS."""
    id: str
    title: str
    event_date: Optional[str] = None


class TestedConceptResponse(BaseModel):
    """Концепт, который эксперимент проверяет (TESTS)."""
    id: str
    name: str


class IntensityMetricsBundleResponse(BaseModel):
    """Средняя интенсивность и точки для графика."""
    average: Optional[float] = None
    data_points: List[IntensityMetricResponse]


class ExperimentDetailResponse(BaseModel):
    """Полная карточка эксперимента для UI."""
    experiment: ExperimentResponse
    intensity_metrics: IntensityMetricsBundleResponse
    related_entries: List[RelatedEntryResponse]
    tested_concepts: List[TestedConceptResponse]


class ExperimentCreateRequest(BaseModel):
    """Request to create an experiment."""
    title: Optional[str] = None
    description: str
    status: str = "active"
    success: int = 0
    outcome: Optional[str] = ""
    goal_id: Optional[UUID] = None
    phase: str = "now"
    due_date: Optional[date] = None
    source: str = "user"


class ExperimentListResponse(BaseModel):
    """List of experiments."""
    experiments: List[ExperimentResponse]


class ExperimentUpdateRequest(BaseModel):
    """Обновление статуса / результата эксперимента."""
    status: Optional[str] = None
    success: Optional[int] = None
    outcome: Optional[str] = None
