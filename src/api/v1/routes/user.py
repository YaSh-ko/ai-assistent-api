from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import sys
import os
from pathlib import Path

def setup_paths():
    current = Path(__file__).resolve()
    root = None
    for parent in current.parents:
        if (parent / "common").exists():
            root = parent
            break
    if root:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
        api_src = root / "API" / "src"
        if api_src.exists() and str(api_src) not in sys.path:
            sys.path.insert(0, str(api_src))

setup_paths()

from common.database.models import User
from src.core.database import get_db

router = APIRouter()

@router.get(
    "/me",
    responses={500: {"description": "Internal server error"}},
)
async def get_current_user_example(db: Annotated[AsyncSession, Depends(get_db)]):
    """
    Example endpoint showing how to fetch data from the shared User model.
    """
    try:
        # Just fetch the first user as a demonstration
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        
        if not user:
            return {"message": "No users found in database. Apply migrations and add a user first."}
            
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "created_at": user.createdAt
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
