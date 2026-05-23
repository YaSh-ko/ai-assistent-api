"""Общие зависимости для API v1 (auth, текущий пользователь)."""
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.exceptions import UnauthorizedException
from src.services.auth_service import AuthService


async def get_current_user_id(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> str:
    """Возвращает ID текущего пользователя по session token (cookie или Authorization)."""
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise UnauthorizedException()
    auth_service = AuthService(db)
    try:
        user, _ = await auth_service.validate_session(token)
        return user.id
    except Exception:
        raise UnauthorizedException()
