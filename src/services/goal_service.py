"""
Goal service — PostgreSQL as source of truth, Neo4j for graph layer.
"""
import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from common.database.models import Goal
from src.data.repositories.goal import GoalRepository
from src.infrastructure.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


async def sync_goal_to_neo4j(goal: Goal) -> None:
    """Mirror Goal to Neo4j. Does not raise on failure."""
    try:
        target_date = goal.target_date.isoformat() if goal.target_date else None
        query = """
        MERGE (g:Goal {id: $id})
        ON CREATE SET g.created_at = datetime()
        SET g.user_id = $user_id,
            g.title = $title,
            g.description = $description,
            g.status = $status,
            g.priority = $priority,
            g.target_date = $target_date,
            g.updated_at = datetime()
        RETURN g
        """
        await neo4j_client.execute_query_async(
            query,
            {
                "id": str(goal.id),
                "user_id": goal.user_id,
                "title": (goal.title or "")[:160],
                "description": goal.description or "",
                "status": goal.status,
                "priority": goal.priority or "medium",
                "target_date": target_date,
            },
        )
        logger.info("Goal %s synced to Neo4j", goal.id)
    except Exception as e:
        logger.error("Error syncing goal to Neo4j: %s", e)


async def create_goal_and_sync(
    db: AsyncSession,
    user_id: str,
    title: str,
    description: str,
    status: str = "active",
    priority: str = "medium",
    target_date: Optional[date] = None,
) -> Goal:
    from src.services.semantic_linker import semantic_link_entity

    goal = Goal(
        user_id=user_id,
        title=title[:500] if title else None,
        description=description,
        status=status,
        priority=priority,
        target_date=target_date,
    )
    repo = GoalRepository(db)
    created = await repo.create(goal)
    await sync_goal_to_neo4j(created)
    await semantic_link_entity(
        entity_id=str(created.id),
        entity_type="goal",
        title=title,
        description=description,
        user_id=user_id,
        db=db,
    )
    return created


async def delete_goal_from_neo4j(goal_id: str) -> None:
    try:
        await neo4j_client.execute_query_async(
            """
            MATCH (g:Goal {id: $id})
            OPTIONAL MATCH (g)-[:DECOMPOSED_INTO]->(e:Experiment)
            DETACH DELETE e, g
            """,
            {"id": goal_id},
        )
        logger.info("Goal %s deleted from Neo4j", goal_id)
    except Exception as e:
        logger.error("Error deleting goal from Neo4j: %s", e)


async def delete_goal_and_sync(db: AsyncSession, goal_id: str, user_id: str) -> bool:
    from uuid import UUID

    try:
        gid = UUID(goal_id)
    except ValueError:
        return False

    repo = GoalRepository(db)
    goal = await repo.get_by_id(gid)
    if not goal or goal.user_id != user_id:
        return False

    deleted = await repo.delete(gid)
    if deleted:
        await delete_goal_from_neo4j(goal_id)
    return deleted
