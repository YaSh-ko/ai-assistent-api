"""Тесты эндпоинтов conversations (с моком репозитория)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.api.v1.deps import get_current_user_id


async def _mock_user_id():
    await asyncio.sleep(0)
    return "user-1"


@pytest.fixture
def app_conv(app):
    app.dependency_overrides[get_current_user_id] = _mock_user_id
    yield app
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def client_conv(app_conv):
    return TestClient(app_conv)


def test_get_conversations_success(client_conv):
    """GET /v1/conversations — 200 и список."""
    with patch("src.api.v1.routes.conversations.ConversationRepository") as Repo:
        repo = MagicMock()
        repo.get_by_user_id = AsyncMock(return_value=[])
        Repo.return_value = repo
        r = client_conv.get("/v1/conversations")
    assert r.status_code == 200
    assert "conversations" in r.json()


def test_get_recent_conversations_success(client_conv):
    """GET /v1/conversations/recent — 200."""
    with patch("src.api.v1.routes.conversations.ConversationRepository") as Repo:
        repo = MagicMock()
        repo.get_recent = AsyncMock(return_value=[])
        Repo.return_value = repo
        r = client_conv.get("/v1/conversations/recent?limit=5")
    assert r.status_code == 200


def test_get_conversation_success(client_conv):
    """GET /v1/conversations/{id} — 200 при своей беседе."""
    from uuid import uuid4
    from datetime import datetime, timezone
    conv_id = uuid4()
    mock_conv = MagicMock()
    mock_conv.id = conv_id
    mock_conv.user_id = "user-1"
    mock_conv.title = "Chat"
    mock_conv.thread_id = "thread-1"
    mock_conv.llm_provider = "openai"
    mock_conv.model = None
    mock_conv.provider_session_id = None
    mock_conv.created_at = datetime.now(timezone.utc)
    mock_conv.last_active_at = datetime.now(timezone.utc)
    with patch("src.api.v1.routes.conversations.ConversationRepository") as Repo:
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=mock_conv)
        Repo.return_value = repo
        r = client_conv.get(f"/v1/conversations/{conv_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Chat"


def test_get_conversation_forbidden(client_conv):
    """GET /v1/conversations/{id} — 403 чужая беседа."""
    from uuid import uuid4
    from datetime import datetime, timezone
    conv_id = uuid4()
    mock_conv = MagicMock()
    mock_conv.id = conv_id
    mock_conv.user_id = "other-user"
    with patch("src.api.v1.routes.conversations.ConversationRepository") as Repo:
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=mock_conv)
        Repo.return_value = repo
        r = client_conv.get(f"/v1/conversations/{conv_id}")
    assert r.status_code == 403


def test_get_conversation_not_found(client_conv):
    """GET /v1/conversations/{id} — 404 если беседа не найдена."""
    from uuid import uuid4
    with patch("src.api.v1.routes.conversations.ConversationRepository") as Repo:
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=None)
        Repo.return_value = repo
        r = client_conv.get(f"/v1/conversations/{uuid4()}")
    assert r.status_code == 404
