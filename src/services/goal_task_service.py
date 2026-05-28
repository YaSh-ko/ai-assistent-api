"""
Goal tasks — experiments linked to a goal (task steps).
"""
import logging
from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.models import Experiment, Goal
from src.data.repositories.experiment import ExperimentRepository
from src.data.repositories.goal import GoalRepository
from src.infrastructure.neo4j_client import neo4j_client
from src.services.experiment_service import (
    create_experiment_and_sync,
    sync_experiment_to_neo4j,
    update_experiment_and_sync,
)
from src.services.goal_service import sync_goal_to_neo4j

logger = logging.getLogger(__name__)

VALID_PHASES = frozenset({"now", "next", "backlog"})


def _utc_naive_now() -> datetime:
    """TIMESTAMP WITHOUT TIME ZONE columns require naive datetimes."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
TASK_STATUS_PENDING = "pending"
TASK_STATUS_COMPLETED = "completed"


def _experiment_status_to_task_status(status: str) -> str:
    return TASK_STATUS_COMPLETED if status == "completed" else TASK_STATUS_PENDING


def _task_status_to_experiment_fields(status: str) -> dict:
    if status == TASK_STATUS_COMPLETED:
        return {"status": "completed", "success": 100, "ended_at": _utc_naive_now()}
    return {"status": "active", "success": 0, "ended_at": None}


async def link_goal_task_in_neo4j(goal_id: str, experiment_id: str) -> None:
    try:
        await neo4j_client.execute_query_async(
            """
            MATCH (g:Goal {id: $goal_id})
            MATCH (e:Experiment {id: $experiment_id})
            MERGE (g)-[r:DECOMPOSED_INTO]->(e)
            ON CREATE SET r.created_at = datetime()
            """,
            {"goal_id": goal_id, "experiment_id": experiment_id},
        )
    except Exception as e:
        logger.warning("Failed to link goal-task in Neo4j: %s", e)


async def sync_goal_completion_from_tasks(db: AsyncSession, goal_id: UUID, user_id: str) -> Optional[Goal]:
    """Mark goal completed when all tasks done; reopen when not."""
    goal_repo = GoalRepository(db)
    goal = await goal_repo.get_by_id(goal_id)
    if not goal or goal.user_id != user_id:
        return None

    result = await db.execute(
        select(
            func.count(Experiment.id),
            func.count(Experiment.id).filter(Experiment.status == "completed"),
        ).where(Experiment.goal_id == goal_id)
    )
    row = result.one()
    total, completed = int(row[0] or 0), int(row[1] or 0)

    if total > 0 and completed == total and goal.status != "completed":
        updated = await goal_repo.update(
            goal_id,
            status="completed",
            achieved_at=_utc_naive_now(),
        )
        await sync_goal_to_neo4j(updated)
        return updated

    if total > 0 and completed < total and goal.status == "completed":
        updated = await goal_repo.update(
            goal_id,
            status="active",
            achieved_at=None,
        )
        await sync_goal_to_neo4j(updated)
        return updated

    return goal


async def create_goal_task(
    db: AsyncSession,
    user_id: str,
    goal_id: UUID,
    title: str,
    description: str = "",
    phase: str = "now",
    due_date: Optional[date] = None,
    source: str = "user",
) -> Experiment:
    phase_norm = phase if phase in VALID_PHASES else "now"
    desc = description or title
    created = await create_experiment_and_sync(
        db=db,
        user_id=user_id,
        title=title,
        description=desc,
        status="active",
        success=0,
        goal_id=goal_id,
        phase=phase_norm,
        due_date=due_date,
        source=source,
    )
    await link_goal_task_in_neo4j(str(goal_id), str(created.id))
    await sync_goal_completion_from_tasks(db, goal_id, user_id)
    return created


async def list_goal_tasks(
    db: AsyncSession,
    goal_id: UUID,
    user_id: str,
) -> List[Experiment]:
    repo = ExperimentRepository(db)
    return await repo.get_by_goal_id(goal_id, user_id)


async def update_goal_task(
    db: AsyncSession,
    goal_id: UUID,
    task_id: UUID,
    user_id: str,
    *,
    title: Optional[str] = None,
    status: Optional[str] = None,
    phase: Optional[str] = None,
    due_date: Optional[date] = None,
) -> Optional[Experiment]:
    repo = ExperimentRepository(db)
    row = await repo.get_by_id(task_id)
    if not row or row.user_id != user_id or row.goal_id != goal_id:
        return None

    fields: dict = {}
    if title is not None:
        fields["title"] = title[:500]
        if not row.description:
            fields["description"] = title
    if phase is not None and phase in VALID_PHASES:
        fields["phase"] = phase
    if due_date is not None:
        fields["due_date"] = due_date
    if status is not None:
        fields.update(_task_status_to_experiment_fields(status))

    if not fields:
        return row

    updated = await update_experiment_and_sync(db, task_id, user_id, **fields)
    if updated:
        await sync_goal_completion_from_tasks(db, goal_id, user_id)
    return updated


async def delete_goal_task(
    db: AsyncSession,
    goal_id: UUID,
    task_id: UUID,
    user_id: str,
) -> bool:
    repo = ExperimentRepository(db)
    row = await repo.get_by_id(task_id)
    if not row or row.user_id != user_id or row.goal_id != goal_id:
        return False
    if row.status == "completed":
        return False
    deleted = await repo.delete(task_id)
    if deleted:
        try:
            await neo4j_client.execute_query_async(
                "MATCH (e:Experiment {id: $id}) DETACH DELETE e",
                {"id": str(task_id)},
            )
        except Exception as e:
            logger.warning("Neo4j task delete failed: %s", e)
        await sync_goal_completion_from_tasks(db, goal_id, user_id)
    return deleted


async def get_goals_task_progress(
    db: AsyncSession,
    user_id: str,
    goal_ids: List[UUID],
) -> dict[str, dict]:
    if not goal_ids:
        return {}
    result = await db.execute(
        select(
            Experiment.goal_id,
            func.count(Experiment.id),
            func.count(Experiment.id).filter(Experiment.status == "completed"),
        )
        .where(Experiment.user_id == user_id, Experiment.goal_id.in_(goal_ids))
        .group_by(Experiment.goal_id)
    )
    out: dict[str, dict] = {}
    for gid, total, completed in result.all():
        if gid is None:
            continue
        total_i = int(total or 0)
        completed_i = int(completed or 0)
        percent = round((completed_i / total_i) * 100) if total_i > 0 else 0
        out[str(gid)] = {
            "total": total_i,
            "completed": completed_i,
            "percent": percent,
        }
    return out
