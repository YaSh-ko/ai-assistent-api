"""
Schemas for audio transcription endpoints.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import date
from uuid import UUID


class TranscriptionResponse(BaseModel):
    """Response for audio transcription."""
    entry_id: UUID
    text: str
    language: str
    duration: float
    created_at: str


class TranscriptionStreamResponse(BaseModel):
    """Response for streaming transcription."""
    text: str
    is_final: bool
    entry_id: Optional[UUID] = None


class TranscriptionRequest(BaseModel):
    """Request for audio transcription."""
    title: Optional[str] = None
    event_date: Optional[date] = None
    conversation_id: Optional[str] = None
