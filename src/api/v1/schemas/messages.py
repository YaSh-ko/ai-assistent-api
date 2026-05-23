"""
Schemas for message endpoints.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class MessageResponse(BaseModel):
    """Message response model."""
    id: UUID
    conversation_id: UUID
    user_id: str
    role: str
    content: str
    meta_data: Optional[str] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class MessageCreateRequest(BaseModel):
    """Request to create a message."""
    content: str
    role: str = "user"
    meta_data: Optional[Dict[str, Any]] = None


class MessageListResponse(BaseModel):
    """List of messages."""
    messages: List[MessageResponse]


class MessageReactionRequest(BaseModel):
    """Request to add a reaction to a message."""
    reaction_type: str
    emoji: Optional[str] = None


class MessageReactionResponse(BaseModel):
    """Message reaction response."""
    id: UUID
    message_id: UUID
    user_id: str
    reaction_type: str
    emoji: Optional[str] = None
    created_at: datetime
    
    model_config = {"from_attributes": True}
