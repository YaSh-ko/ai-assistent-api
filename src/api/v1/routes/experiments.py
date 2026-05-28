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
from src.data.repositories.experiment import ExperimentRepository
from src.data.repositories.metrics import IntensityMetricRepository
from src.infrastructure.neo4j_client import neo4j_client
from src.services.entity_serializers import experiment_to_response
from src.services.experiment_service import (
    create_experiment_and_sync,
    update_experiment_and_sync,
)
from src.api.v1.schemas.experiments import (
    ExperimentDetailResponse,
    ExperimentResponse,
    ExperimentSummaryResponse,
    ExperimentListResponse,
    ExperimentCreateRequest,
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


async def _get_experiment_response(
    experiment_id: str,
    user_id: str,
    db: AsyncSession,
) -> ExperimentResponse:
    """Load experiment from PostgreSQL, fallback to legacy Neo4j-only nodes."""
    try:
        eid = UUID(experiment_id)
        repo = ExperimentRepository(db)
        row = await repo.get_by_id(eid)
        if row and row.user_id == user_id:
            return experiment_to_response(row)
    except ValueError:
        pass

    node = await neo4j_client.get_node_by_id(experiment_id, "Experiment")
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EXPERIMENT_NOT_FOUND,
        )
    if node.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    return ExperimentResponse(**node)


@router.get("", response_model=ExperimentListResponse)
async def list_experiments(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
):
    """List experiments from PostgreSQL."""
    repo = ExperimentRepository(db)
    rows = await repo.get_by_user_id(user_id, skip=skip, limit=limit)
    return ExperimentListResponse(
        experiments=[experiment_to_response(e) for e in rows]
    )


@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    request: ExperimentCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create experiment in PostgreSQL and sync to Neo4j."""
    created = await create_experiment_and_sync(
        db=db,
        user_id=user_id,
        title=request.title or "",
        description=request.description,
        status=request.status,
        success=request.success,
        outcome=request.outcome or "",
        goal_id=request.goal_id,
        phase=request.phase,
        due_date=request.due_date,
        source=request.source,
    )
    if request.goal_id:
        from src.services.goal_task_service import link_goal_task_in_neo4j, sync_goal_completion_from_tasks
        await link_goal_task_in_neo4j(str(request.goal_id), str(created.id))
        await sync_goal_completion_from_tasks(db, request.goal_id, user_id)
    return experiment_to_response(created)


@router.get("/{id}", response_model=ExperimentDetailResponse)
async def get_experiment(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Эксперимент с метриками, связанными записями и концептами."""
    experiment_resp = await _get_experiment_response(id, user_id, db)

    metrics = []
    entity_id = _entity_uuid_for_postgres(experiment_resp.id)
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
        experiment=experiment_resp,
        intensity_metrics=_metrics_bundle_from_models(metrics),
        related_entries=related_entries,
        tested_concepts=tested_concepts,
    )


@router.put("/{id}", response_model=ExperimentResponse)
async def update_experiment(
    id: str,
    body: ExperimentUpdateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update experiment in PostgreSQL (and Neo4j sync) or legacy Neo4j-only node."""
    entity_id = _entity_uuid_for_postgres(id)
    if entity_id is not None:
        updated = await update_experiment_and_sync(
            db,
            entity_id,
            user_id,
            status=body.status,
            success=body.success,
            outcome=body.outcome,
        )
        if updated:
            return experiment_to_response(updated)

    await _get_experiment_response(id, user_id, db)
    updated_node = await neo4j_client.update_experiment_node(
        id,
        user_id,
        status=body.status,
        success=body.success,
        outcome=body.outcome,
    )
    if not updated_node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_EXPERIMENT_NOT_FOUND,
        )
    return ExperimentResponse(**dict(updated_node))


@router.get("/{id}/intensity-metrics", response_model=list[IntensityMetricResponse])
async def get_experiment_intensity_metrics(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: Annotated[Optional[str], Query(description="week, month, year")] = None,
):
    """Метрики интенсивности; при period — только за выбранный интервал."""
    experiment_resp = await _get_experiment_response(id, user_id, db)
    entity_id = _entity_uuid_for_postgres(experiment_resp.id)
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
    experiment_resp = await _get_experiment_response(id, user_id, db)
    entity_id = _entity_uuid_for_postgres(experiment_resp.id)
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
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get entries that document an experiment."""
    await _get_experiment_response(id, user_id, db)
    entries = await neo4j_client.get_entries_documenting_experiment(id)
    return [EntryForExperimentResponse(**entry) for entry in entries]


@router.get("/{id}/summary", response_model=ExperimentSummaryResponse)
async def get_experiment_summary(
    id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get experiment summary with metrics."""
    experiment_resp = await _get_experiment_response(id, user_id, db)
    entity_id = _entity_uuid_for_postgres(experiment_resp.id)
    if entity_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MSG_INVALID_EXPERIMENT_ID
        )

    metrics_repo = IntensityMetricRepository(db)
    metrics = await metrics_repo.get_by_entity("experiment", entity_id)
    avg_intensity = await metrics_repo.get_average_intensity("experiment", entity_id)

    return ExperimentSummaryResponse(
        experiment=experiment_resp,
        average_intensity=avg_intensity if avg_intensity > 0 else None,
        intensity_metrics=[IntensityMetricResponse.model_validate(m).model_dump() for m in metrics]
    )
