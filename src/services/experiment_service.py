"""
Experiment service — PostgreSQL as source of truth, Neo4j for graph layer.
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from common.database.models import Experiment
from src.data.repositories.experiment import ExperimentRepository
from src.infrastructure.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


async def sync_experiment_to_neo4j(experiment: Experiment) -> None:
    """Mirror Experiment to Neo4j. Does not raise on failure."""
    try:
        started_at = experiment.started_at or experiment.created_at
        query = """
        MERGE (e:Experiment {id: $id})
        ON CREATE SET e.created_at = datetime(), e.started_at = datetime()
        SET e.user_id = $user_id,
            e.title = $title,
            e.description = $description,
            e.status = $status,
            e.success = $success,
            e.outcome = $outcome,
            e.updated_at = datetime()
        RETURN e
        """
        await neo4j_client.execute_query_async(
            query,
            {
                "id": str(experiment.id),
                "user_id": experiment.user_id,
                "title": (experiment.title or "")[:160],
                "description": experiment.description or "",
                "status": experiment.status,
                "success": experiment.success,
                "outcome": experiment.outcome or "",
            },
        )
        logger.info("Experiment %s synced to Neo4j", experiment.id)
    except Exception as e:
        logger.error("Error syncing experiment to Neo4j: %s", e)


async def create_experiment_and_sync(
    db: AsyncSession,
    user_id: str,
    title: str,
    description: str,
    status: str = "active",
    success: int = 0,
    outcome: str = "",
    started_at: Optional[datetime] = None,
) -> Experiment:
    from src.services.semantic_linker import semantic_link_entity

    experiment = Experiment(
        user_id=user_id,
        title=title[:500] if title else None,
        description=description,
        status=status,
        success=success,
        outcome=outcome or "",
        started_at=started_at,
    )
    repo = ExperimentRepository(db)
    created = await repo.create(experiment)
    await sync_experiment_to_neo4j(created)
    await semantic_link_entity(
        entity_id=str(created.id),
        entity_type="task",
        title=title,
        description=description,
        user_id=user_id,
    )
    return created


async def update_experiment_and_sync(
    db: AsyncSession,
    experiment_id: UUID,
    user_id: str,
    **fields,
) -> Optional[Experiment]:
    """Update experiment in PostgreSQL and mirror to Neo4j."""
    repo = ExperimentRepository(db)
    row = await repo.get_by_id(experiment_id)
    if not row or row.user_id != user_id:
        return None
    clean = {k: v for k, v in fields.items() if v is not None}
    if not clean:
        return row
    updated = await repo.update(experiment_id, **clean)
    if updated:
        await sync_experiment_to_neo4j(updated)
    return updated
