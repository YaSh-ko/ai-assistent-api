"""Schemas for goal tasks (experiments linked to goals)."""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class GoalTaskResponse(BaseModel):
    id: str
    goal_id: str
    title: str
    description: Optional[str] = None
    status: str  # pending | completed
    phase: str
    due_date: Optional[date] = None
    source: str = "user"
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @field_validator("created_at", "completed_at", mode="before")
    @classmethod
    def coerce_dt(cls, v):
        if v is None:
            return None
        if hasattr(v, "to_native"):
            return v.to_native()
        return v


class GoalTaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    phase: str = "now"
    due_date: Optional[date] = None
    source: str = "user"


class GoalTaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    phase: Optional[str] = None
    due_date: Optional[date] = None


class GoalTaskListResponse(BaseModel):
    tasks: List[GoalTaskResponse]


class GoalProgressItem(BaseModel):
    goal_id: str
    total: int
    completed: int
    percent: int


class GoalsProgressResponse(BaseModel):
    items: List[GoalProgressItem]


class GoalTaskSuggestExistingItem(BaseModel):
    title: str
    status: str = ""
    phase: str = ""


class GoalTaskSuggestedItem(BaseModel):
    title: str
    phase: str = "now"
    description: Optional[str] = None


class GoalTaskSuggestResponse(BaseModel):
    tasks: List[GoalTaskSuggestedItem]
