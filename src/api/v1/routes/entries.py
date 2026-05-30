"""
Entry endpoints.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.models import Entry, IntensityMetric, RelatedSituation, NegativeImpact, Transformation
from src.api.v1.deps import get_current_user_id
from src.core.database import get_db
from src.data.repositories.entry import EntryRepository
from src.data.repositories.metrics import IntensityMetricRepository
from src.data.repositories.related_situation import RelatedSituationRepository
from src.data.repositories.negative_impact import NegativeImpactRepository
from src.data.repositories.transformation import TransformationRepository
from src.infrastructure.neo4j_client import neo4j_client
from src.services.entry_service import create_entry_and_sync, delete_entry_and_sync
from src.api.v1.schemas.entries import (
    EntryResponse,
    EntryListResponse,
    EntryCreateRequest,
    EntryPatchRequest,
    EntryAnalysisResponse,
    IntensityMetricResponse,
    RelatedSituationResponse,
    NegativeImpactResponse,
    NegativeImpactCreateRequest,
    TransformationResponse,
    TransformationCreateRequest,
)

router = APIRouter()

MSG_ENTRY_NOT_FOUND = "Entry not found"


@router.get("", response_model=EntryListResponse)
async def get_entries(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
):
    """Get list of entries."""
    repo = EntryRepository(db)
    entries = await repo.get_by_user_id(user_id, skip=skip, limit=limit)
    return EntryListResponse(
        entries=[EntryResponse.model_validate(e) for e in entries]
    )


@router.get("/recent", response_model=EntryListResponse)
async def get_recent_entries(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
):
    """Get recent entries."""
    repo = EntryRepository(db)
    entries = await repo.get_recent(user_id, limit=limit)
    return EntryListResponse(
        entries=[EntryResponse.model_validate(e) for e in entries]
    )


@router.post("", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    request: EntryCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new entry (DB + Neo4j sync; ChromaDB can be added in entry_service)."""
    created = await create_entry_and_sync(
        db=db,
        user_id=user_id,
        title=request.title or "",
        description=request.description,
        event_date=request.event_date,
    )
    return EntryResponse.model_validate(created)


@router.get("/{id}/analysis", response_model=EntryAnalysisResponse)
async def get_entry_analysis(
    id: UUID,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get complete analysis for an entry."""
    entry_repo = EntryRepository(db)
    entry = await entry_repo.get_by_id(id)
    
    if not entry or entry.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ENTRY_NOT_FOUND
        )
    
    # Get intensity metrics
    metrics_repo = IntensityMetricRepository(db)
    metrics = await metrics_repo.get_by_entity("entry", id)
    
    # Get related situations
    related_repo = RelatedSituationRepository(db)
    related = await related_repo.get_by_source("entry", id)
    
    # Get negative impacts
    impact_repo = NegativeImpactRepository(db)
    impacts = await impact_repo.get_by_source("entry", id)
    
    # Get transformations
    trans_repo = TransformationRepository(db)
    transformations = await trans_repo.get_by_source("entry", id)
    
    # Get concepts from Neo4j
    concepts = await neo4j_client.get_related_nodes(str(id), "MENTIONS", "Concept")
    
    return EntryAnalysisResponse(
        entry=EntryResponse.model_validate(entry),
        intensity_metrics=[IntensityMetricResponse.model_validate(m) for m in metrics],
        related_situations=[RelatedSituationResponse.model_validate(r) for r in related],
        negative_impacts=[NegativeImpactResponse.model_validate(i) for i in impacts],
        transformations=[TransformationResponse.model_validate(t) for t in transformations],
        concepts=concepts
    )


@router.get("/{id}/intensity-metrics", response_model=list[IntensityMetricResponse])
async def get_entry_intensity_metrics(
    id: UUID,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get intensity metrics for an entry."""
    entry_repo = EntryRepository(db)
    entry = await entry_repo.get_by_id(id)
    
    if not entry or entry.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ENTRY_NOT_FOUND
        )
    
    metrics_repo = IntensityMetricRepository(db)
    metrics = await metrics_repo.get_by_entity("entry", id)
    return [IntensityMetricResponse.model_validate(m) for m in metrics]


@router.get("/{id}/related-situations", response_model=list[RelatedSituationResponse])
async def get_entry_related_situations(
    id: UUID,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get related situations for an entry."""
    entry_repo = EntryRepository(db)
    entry = await entry_repo.get_by_id(id)
    
    if not entry or entry.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ENTRY_NOT_FOUND
        )
    
    related_repo = RelatedSituationRepository(db)
    related = await related_repo.get_by_source("entry", id)
    return [RelatedSituationResponse.model_validate(r) for r in related]


@router.get("/{id}/negative-impacts", response_model=list[NegativeImpactResponse])
async def get_entry_negative_impacts(
    id: UUID,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get negative impacts for an entry."""
    entry_repo = EntryRepository(db)
    entry = await entry_repo.get_by_id(id)
    
    if not entry or entry.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ENTRY_NOT_FOUND
        )
    
    impact_repo = NegativeImpactRepository(db)
    impacts = await impact_repo.get_by_source("entry", id)
    return [NegativeImpactResponse.model_validate(i) for i in impacts]


@router.get("/{id}/transformations", response_model=list[TransformationResponse])
async def get_entry_transformations(
    id: UUID,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get transformations for an entry."""
    entry_repo = EntryRepository(db)
    entry = await entry_repo.get_by_id(id)
    
    if not entry or entry.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MSG_ENTRY_NOT_FOUND
        )
    
    trans_repo = TransformationRepository(db)
    transformations = await trans_repo.get_by_source("entry", id)
    return [TransformationResponse.model_validate(t) for t in transformations]


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    id: UUID,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete an entry and remove it from the graph."""
    deleted = await delete_entry_and_sync(db, str(id), user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_ENTRY_NOT_FOUND)


@router.patch("/{id}", response_model=EntryResponse)
async def patch_entry(
    id: UUID,
    request: EntryPatchRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Partially update an entry (silent enrichment from chat detector)."""
    entry_repo = EntryRepository(db)
    entry = await entry_repo.get_by_id(id)

    if not entry or entry.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_ENTRY_NOT_FOUND)

    update_kwargs = request.model_dump(exclude_none=True)
    if not update_kwargs:
        return EntryResponse.model_validate(entry)

    updated = await entry_repo.update(id, **update_kwargs)
    return EntryResponse.model_validate(updated)


@router.post("/{id}/negative-impacts", response_model=NegativeImpactResponse, status_code=status.HTTP_201_CREATED)
async def create_negative_impact(
    id: UUID,
    request: NegativeImpactCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a negative impact for an entry (red block on event page)."""
    entry_repo = EntryRepository(db)
    entry = await entry_repo.get_by_id(id)

    if not entry or entry.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_ENTRY_NOT_FOUND)

    impact_repo = NegativeImpactRepository(db)
    impact = NegativeImpact(
        user_id=user_id,
        source_type="entry",
        source_id=id,
        title=request.title,
        description=request.description,
        severity=request.severity,
    )
    created = await impact_repo.create(impact)
    return NegativeImpactResponse.model_validate(created)


@router.post("/{id}/transformations", response_model=TransformationResponse, status_code=status.HTTP_201_CREATED)
async def create_transformation(
    id: UUID,
    request: TransformationCreateRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a transformation for an entry (green block on event page)."""
    entry_repo = EntryRepository(db)
    entry = await entry_repo.get_by_id(id)

    if not entry or entry.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_ENTRY_NOT_FOUND)

    trans_repo = TransformationRepository(db)
    transformation = Transformation(
        user_id=user_id,
        source_type="entry",
        source_id=id,
        title=request.title,
        description=request.description,
        category=request.category,
    )
    created = await trans_repo.create(transformation)
    return TransformationResponse.model_validate(created)
