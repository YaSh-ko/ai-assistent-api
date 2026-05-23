"""
Schemas for analytics insights endpoints.
"""
from pydantic import BaseModel
from typing import List


class EntryPatternItem(BaseModel):
    """Single repeating pattern item."""
    label: str
    count: int


class EntryInsightsResponse(BaseModel):
    """Aggregated insights for entries by period."""
    period: str
    total_entries: int
    active_days: int
    average_entries_per_active_day: float
    average_text_length: float
    strongest_entry_title: str
    strongest_entry_length: int
    growth_triggers: List[EntryPatternItem]
    burnout_triggers: List[EntryPatternItem]
    repeating_patterns: List[EntryPatternItem]
