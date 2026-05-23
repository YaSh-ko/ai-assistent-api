"""Тесты общих зависимостей API v1."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request

from src.api.v1.deps import get_current_user_id
from src.core.exceptions import UnauthorizedException


@pytest.mark.asyncio
async def test_get_current_user_id_no_token_raises():
    """Без cookie и Authorization — UnauthorizedException."""
    request = MagicMock(spec=Request)
    request.cookies = {}
    request.headers = {}
    db = AsyncMock()
    with pytest.raises(UnauthorizedException):
        await get_current_user_id(request, db)


@pytest.mark.asyncio
async def test_get_current_user_id_success_returns_user_id():
    """При валидном токене возвращается user.id."""
    request = MagicMock(spec=Request)
    request.cookies = {"session_token": "valid-token"}
    request.headers = {}
    db = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = "user-123"
    with patch("src.api.v1.deps.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.validate_session = AsyncMock(return_value=(mock_user, MagicMock()))
        AuthServiceCls.return_value = auth_svc
        result = await get_current_user_id(request, db)
    assert result == "user-123"
    auth_svc.validate_session.assert_called_once_with("valid-token")


@pytest.mark.asyncio
async def test_get_current_user_id_bearer_used():
    """Токен из Authorization: Bearer передаётся в validate_session."""
    request = MagicMock(spec=Request)
    request.cookies = {}
    request.headers = {"Authorization": "Bearer bearer-token"}
    db = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = "user-456"
    with patch("src.api.v1.deps.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.validate_session = AsyncMock(return_value=(mock_user, MagicMock()))
        AuthServiceCls.return_value = auth_svc
        result = await get_current_user_id(request, db)
    assert result == "user-456"
    auth_svc.validate_session.assert_called_once_with("bearer-token")


@pytest.mark.asyncio
async def test_get_current_user_id_validate_raises_unauthorized():
    """При исключении из validate_session — UnauthorizedException."""
    request = MagicMock(spec=Request)
    request.cookies = {"session_token": "bad"}
    request.headers = {}
    db = AsyncMock()
    with patch("src.api.v1.deps.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.validate_session = AsyncMock(side_effect=Exception("any"))
        AuthServiceCls.return_value = auth_svc
        with pytest.raises(UnauthorizedException):
            await get_current_user_id(request, db)
