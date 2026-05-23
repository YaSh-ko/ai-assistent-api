"""
Schemas for markdown import endpoints.
"""
from datetime import date
from pydantic import BaseModel, Field
from typing import List


class MarkdownImportRequest(BaseModel):
    """Import markdown into entities."""
    markdown: str = Field(min_length=1)
    create_entries: bool
    create_goals: bool
    create_experiments: bool
    event_date: date


class CreatedEntityRef(BaseModel):
    """Created entity reference."""
    id: str
    title: str
    entity_type: str


class MarkdownImportResponse(BaseModel):
    """Import result."""
    entries_created: int
    goals_created: int
    experiments_created: int
    created_entities: List[CreatedEntityRef]
