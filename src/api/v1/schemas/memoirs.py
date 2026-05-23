"""
Schemas for memoirs endpoints.
"""
from pydantic import BaseModel, Field
from typing import List


class PublicMemoirItem(BaseModel):
    """Public memoir feed item."""
    id: str
    title: str
    content: str
    author_id: str
    created_at: str
    likes: int


class PublicMemoirCreateRequest(BaseModel):
    """Create public memoir post."""
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1)


class PublicMemoirCreateResponse(BaseModel):
    """Create public memoir response."""
    id: str
    title: str
    content: str
    author_id: str
    created_at: str
    likes: int


class PublicMemoirsFeedResponse(BaseModel):
    """Public memoir feed response."""
    items: List[PublicMemoirItem]


class MemoirRecommendationItem(BaseModel):
    """Recommendation item."""
    title: str
    description: str


class MemoirRecommendationsResponse(BaseModel):
    """Recommendations response."""
    items: List[MemoirRecommendationItem]


class PrivateStoryResponse(BaseModel):
    """Private memoir story response."""
    title: str
    narrative: str
    timeline_points: List[str]
