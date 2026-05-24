"""
Map PostgreSQL ORM entities to API response schemas (Neo4j-compatible shape).
"""
from common.database.models import Experiment, Goal
from src.api.v1.schemas.experiments import ExperimentResponse
from src.api.v1.schemas.goals import GoalResponse


def goal_to_response(goal: Goal) -> GoalResponse:
    return GoalResponse(
        id=str(goal.id),
        title=goal.title or "",
        description=goal.description,
        status=goal.status,
        priority=goal.priority,
        target_date=goal.target_date,
        achieved_at=goal.achieved_at,
        user_id=goal.user_id,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


def experiment_to_response(experiment: Experiment) -> ExperimentResponse:
    return ExperimentResponse(
        id=str(experiment.id),
        title=experiment.title or "",
        description=experiment.description,
        status=experiment.status,
        started_at=experiment.started_at or experiment.created_at,
        ended_at=experiment.ended_at,
        outcome=experiment.outcome,
        success=experiment.success,
        user_id=experiment.user_id,
        created_at=experiment.created_at,
        updated_at=experiment.updated_at,
    )
