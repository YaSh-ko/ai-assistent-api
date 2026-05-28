from common.database.models import Experiment
from src.api.v1.schemas.goal_tasks import GoalTaskResponse


def experiment_to_goal_task(exp: Experiment) -> GoalTaskResponse:
    status = "completed" if exp.status == "completed" else "pending"
    return GoalTaskResponse(
        id=str(exp.id),
        goal_id=str(exp.goal_id) if exp.goal_id else "",
        title=exp.title or "",
        description=exp.description,
        status=status,
        phase=exp.phase or "now",
        due_date=exp.due_date,
        source=exp.source or "user",
        created_at=exp.created_at,
        completed_at=exp.ended_at,
    )
