"""
Schemas for conversation endpoints.
"""
from pydantic import BaseModel, field_validator, model_validator
from typing import List, Literal, Optional
from datetime import datetime
from uuid import UUID

_VALID_CATEGORIES = {"entry", "goal", "experiment", "analysis", "general"}


class ConversationResponse(BaseModel):
    """Conversation response model."""
    id: UUID
    user_id: str
    thread_id: str
    llm_provider: str
    model: Optional[str] = None
    provider_session_id: Optional[str] = None
    title: Optional[str] = None
    category: str = "general"
    created_at: datetime
    last_active_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_category_from_meta_data(cls, data):
        """Read category from meta_data JSONB before field validation."""
        if hasattr(data, "meta_data"):
            meta = data.meta_data or {}
            if isinstance(meta, dict):
                data.__dict__["category"] = meta.get("category", "general")
        return data

    @field_validator("category", mode="before")
    @classmethod
    def coerce_category(cls, v):
        """Coerce unknown category values to 'general'."""
        return v if v in _VALID_CATEGORIES else "general"


class ConversationListResponse(BaseModel):
    """List of conversations."""
    conversations: List[ConversationResponse]


class CreateCategoryConversationRequest(BaseModel):
    """Request to create a conversation pre-assigned to a category."""
    category: Literal["entry", "goal", "experiment", "analysis", "general"]


class CategoryConversationResponse(BaseModel):
    """Response after creating a category conversation."""
    thread_id: str
    conversation_id: str


class ThreadContextResponse(BaseModel):
    """Context information for a conversation thread based on linked entries/events."""
    type: str
    title: str
    description: Optional[str] = None
    entry_id: Optional[UUID] = None


class UpdateThreadCategoryRequest(BaseModel):
    """Request to update the category of a conversation thread."""
    category: Literal["entry", "goal", "experiment", "analysis", "general"]
