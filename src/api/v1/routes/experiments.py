"""
Experiment endpoints.
"""
import re
from datetime import date, datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.models import IntensityMetric
from src.api.v1.deps import get_current_user_id
from src.core.database import get_db
from src.data.repositories.metrics import IntensityMetricRepository
from src.infrastructure.neo4j_client import neo4j_client
from src.api.v1.schemas.experiments import (
    ExperimentDetailResponse,
    ExperimentResponse,
    ExperimentSummaryResponse,
    EntryForExperimentResponse,
    ExperimentUpdateRequest,
    IntensityMetricsBundleResponse,
    RelatedEntryResponse,
    TestedConceptResponse,
)
from src.api.v1.schemas.entries import IntensityMetricResponse, IntensityMetricCreateRequest

router = APIRouter()

MSG_EXPERIMENT_NOT_FOUND = "Experiment not found"
MSG_INVALID_EXPERIMENT_ID = "Invalid experiment ID format"

_UUID_IN_STRING = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _entity_uuid_for_postgres(experiment_id: str) -> Optional[UUID]:
    """Neo4j id может быть строкой вида prefix_uuid; в PG entity_id — UUID."""
    try:
        return UUID(experiment_id)
    except ValueError:
        m = _UUID_IN_STRING.search(experiment_id)
        if m:
            try:
                return UUID(m.group(0))
            except ValueError:
                return None
    return None


def _neo4j_value_to_date_str(val) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, datetime):
        return val.date().isoformat()
    if hasattr(val, "to_native"):
        native = val.to_native()
        if isinstance(native, datetime):
            return native.date().isoformat()
        if isinstance(native, date):
            return native.isoformat()
    if isinstance(val, str):
        return val[:10]
    return None


def _entry_node_to_related(entry: dict) -> RelatedEntryResponse:
    raw_id = entry.get("id")
    eid = str(raw_id) if raw_id is not None else ""
    title = (entry.get("title") or entry.get("content_summary") or "").strip()
    if not title:
        content = entry.get("content") or ""
        title = content[:200] + ("…" if len(content) > 200 else "")
    event_date = _neo4j_value_to_date_str(entry.get("event_date"))
    if not event_date:
        event_date = _neo4j_value_to_date_str(entry.get("timestamp"))
    return RelatedEntryResponse(id=eid, title=title or "Запись", event_date=event_date)


def _metrics_bundle_from_models(metrics: list) -> IntensityMetricsBundleResponse:
    if not metrics:
        return IntensityMetricsBundleResponse(average=None, data_points=[])
    avg = sum(m.intensity_value for m in metrics) / len(metrics)
    return IntensityMetricsBundleResponse(
        average=avg,
        data_points=[IntensityMetricResponse.model_validate(m) for m in metrics],
    )


@router.get("/{id}", response_model=ExperimentDetailResponse)
async def get_experiment(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Эксперимент с метриками, связанными записями и концептами."""
    experiment = await neo4j_client.get_node_by_id(id, "Experiment")
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EXPERIMENT_NOT_FOUND
        )
    if experiment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    metrics = []
    entity_id = _entity_uuid_for_postgres(id)
    if entity_id is not None:
        metrics_repo = IntensityMetricRepository(db)
        metrics = await metrics_repo.get_by_entity("experiment", entity_id)

    entry_nodes = await neo4j_client.get_entries_documenting_experiment(id)
    related_entries = [_entry_node_to_related(e) for e in entry_nodes]

    concept_nodes = await neo4j_client.get_related_nodes(id, "TESTS", "Concept")
    tested_concepts = [
        TestedConceptResponse(id=str(c.get("id", "")), name=c.get("name") or "")
        for c in concept_nodes
        if c.get("id") is not None
    ]

    return ExperimentDetailResponse(
        experiment=ExperimentResponse(**experiment),
        intensity_metrics=_metrics_bundle_from_models(metrics),
        related_entries=related_entries,
        tested_concepts=tested_concepts,
    )


@router.put("/{id}", response_model=ExperimentResponse)
async def update_experiment(
    id: str,
    body: ExperimentUpdateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Обновить status, success, outcome эксперимента в Neo4j."""
    experiment = await neo4j_client.get_node_by_id(id, "Experiment")
    if not experiment or experiment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EXPERIMENT_NOT_FOUND
        )

    updated = await neo4j_client.update_experiment_node(
        id,
        user_id,
        status=body.status,
        success=body.success,
        outcome=body.outcome,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EXPERIMENT_NOT_FOUND
        )
    return ExperimentResponse(**dict(updated))


@router.get("/{id}/intensity-metrics", response_model=list[IntensityMetricResponse])
async def get_experiment_intensity_metrics(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: Annotated[Optional[str], Query(description="week, month, year")] = None,
):
    """Метрики интенсивности; при period — только за выбранный интервал."""
    experiment = await neo4j_client.get_node_by_id(id, "Experiment")
    if not experiment or experiment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EXPERIMENT_NOT_FOUND
        )

    entity_id = _entity_uuid_for_postgres(id)
    if entity_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MSG_INVALID_EXPERIMENT_ID
        )

    metrics_repo = IntensityMetricRepository(db)
    if period in ("week", "month", "year"):
        metrics = await metrics_repo.get_by_entity_period("experiment", entity_id, period)
    else:
        metrics = await metrics_repo.get_by_entity("experiment", entity_id)
    return [IntensityMetricResponse.model_validate(m) for m in metrics]


@router.post("/{id}/intensity-metrics", response_model=IntensityMetricResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment_intensity_metric(
    id: str,
    request: IntensityMetricCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Add an intensity metric for an experiment."""
    experiment = await neo4j_client.get_node_by_id(id, "Experiment")
    if not experiment or experiment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EXPERIMENT_NOT_FOUND
        )

    entity_id = _entity_uuid_for_postgres(id)
    if entity_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MSG_INVALID_EXPERIMENT_ID
        )

    metric = IntensityMetric(
        user_id=user_id,
        entity_type="experiment",
        entity_id=entity_id,
        intensity_value=request.intensity_value,
        metric_date=request.metric_date,
        note=request.note
    )

    db.add(metric)
    await db.commit()
    await db.refresh(metric)

    return IntensityMetricResponse.model_validate(metric)


@router.get("/{id}/entries", response_model=list[EntryForExperimentResponse])
async def get_experiment_entries(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Get entries that document an experiment."""
    experiment = await neo4j_client.get_node_by_id(id, "Experiment")
    if not experiment or experiment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EXPERIMENT_NOT_FOUND
        )

    entries = await neo4j_client.get_entries_documenting_experiment(id)
    return [EntryForExperimentResponse(**entry) for entry in entries]


@router.get("/{id}/summary", response_model=ExperimentSummaryResponse)
async def get_experiment_summary(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get experiment summary with metrics."""
    experiment = await neo4j_client.get_node_by_id(id, "Experiment")
    if not experiment or experiment.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EXPERIMENT_NOT_FOUND
        )

    entity_id = _entity_uuid_for_postgres(id)
    if entity_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MSG_INVALID_EXPERIMENT_ID
        )

    metrics_repo = IntensityMetricRepository(db)
    metrics = await metrics_repo.get_by_entity("experiment", entity_id)
    avg_intensity = await metrics_repo.get_average_intensity("experiment", entity_id)

    return ExperimentSummaryResponse(
        experiment=ExperimentResponse(**experiment),
        average_intensity=avg_intensity if avg_intensity > 0 else None,
        intensity_metrics=[IntensityMetricResponse.model_validate(m).model_dump() for m in metrics]
    )
