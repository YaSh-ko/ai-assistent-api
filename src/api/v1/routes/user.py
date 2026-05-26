from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.database.models import User
from src.api.v1.deps import get_current_user_id
from src.core.database import get_db

router = APIRouter()


@router.get("/me")
async def get_current_user(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "ai_persona_tone": user.ai_persona_tone,
        "ai_persona_role": user.ai_persona_role,
        "created_at": user.createdAt,
    }


class PersonaPatchRequest(BaseModel):
    ai_persona_tone: Optional[str] = None
    ai_persona_role: Optional[str] = None


@router.patch("/me/persona")
async def patch_persona(
    request: PersonaPatchRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if request.ai_persona_tone is not None:
        user.ai_persona_tone = request.ai_persona_tone
    if request.ai_persona_role is not None:
        user.ai_persona_role = request.ai_persona_role

    await db.commit()
    return {
        "ai_persona_tone": user.ai_persona_tone,
        "ai_persona_role": user.ai_persona_role,
    }


@router.get("/me/persona")
async def get_persona(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "ai_persona_tone": user.ai_persona_tone,
        "ai_persona_role": user.ai_persona_role,
    }
