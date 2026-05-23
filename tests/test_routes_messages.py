"""Тесты эндпоинтов messages (get_messages с моками)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from fastapi.testclient import TestClient

from src.api.v1.deps import get_current_user_id


async def _mock_user_id():
    await asyncio.sleep(0)
    return "user-1"


@pytest.fixture
def app_messages(app):
    app.dependency_overrides[get_current_user_id] = _mock_user_id
    yield app
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def client_messages(app_messages):
    return TestClient(app_messages)


def test_get_messages_success(client_messages):
    """GET /v1/conversations/{id}/messages — 200 при своей беседе."""
    conv_id = uuid4()
    with patch("src.api.v1.routes.messages.ConversationRepository") as ConvRepo:
        with patch("src.api.v1.routes.messages.MessageRepository") as MsgRepo:
            mock_conv = MagicMock()
            mock_conv.user_id = "user-1"
            ConvRepo.return_value.get_by_id = AsyncMock(return_value=mock_conv)
            MsgRepo.return_value.get_by_conversation_id = AsyncMock(return_value=[])
            r = client_messages.get(f"/v1/conversations/{conv_id}/messages")
    assert r.status_code == 200
    assert "messages" in r.json()


def test_get_messages_conversation_not_found(client_messages):
    """GET /v1/conversations/{id}/messages — 404 если беседа не найдена."""
    conv_id = uuid4()
    with patch("src.api.v1.routes.messages.ConversationRepository") as ConvRepo:
        ConvRepo.return_value.get_by_id = AsyncMock(return_value=None)
        r = client_messages.get(f"/v1/conversations/{conv_id}/messages")
    assert r.status_code == 404


def test_add_reaction_success(client_messages):
    """POST /v1/messages/{id}/reactions — 201."""
    from uuid import uuid4
    from datetime import datetime, timezone
    msg_id = uuid4()
    conv_id = uuid4()
    mock_msg = MagicMock()
    mock_msg.id = msg_id
    mock_msg.conversation_id = conv_id
    mock_conv = MagicMock()
    mock_conv.user_id = "user-1"
    mock_reaction = MagicMock()
    mock_reaction.id = uuid4()
    mock_reaction.message_id = msg_id
    mock_reaction.user_id = "user-1"
    mock_reaction.reaction_type = "like"
    mock_reaction.emoji = "👍"
    mock_reaction.created_at = datetime.now(timezone.utc)
    with patch("src.api.v1.routes.messages.MessageRepository") as MRepo:
        with patch("src.api.v1.routes.messages.ConversationRepository") as CRepo:
            with patch("src.api.v1.routes.messages.MessageReaction", return_value=mock_reaction):
                MRepo.return_value.get_by_id = AsyncMock(return_value=mock_msg)
                CRepo.return_value.get_by_id = AsyncMock(return_value=mock_conv)
                r = client_messages.post(
                    f"/v1/messages/{msg_id}/reactions",
                    json={"reaction_type": "like", "emoji": "👍"},
                )
    assert r.status_code == 201


def test_add_reaction_message_not_found(client_messages):
    """POST /v1/messages/{id}/reactions — 404 если сообщение не найдено."""
    with patch("src.api.v1.routes.messages.MessageRepository") as MRepo:
        MRepo.return_value.get_by_id = AsyncMock(return_value=None)
        r = client_messages.post(
            f"/v1/messages/{uuid4()}/reactions",
            json={"reaction_type": "like"},
        )
    assert r.status_code == 404


def test_create_message_conversation_not_found_404(client_messages):
    """POST /v1/conversations/{id}/messages — 404 если беседа не найдена."""
    conv_id = uuid4()
    with patch("src.api.v1.routes.messages.ConversationRepository") as ConvRepo:
        ConvRepo.return_value.get_by_id = AsyncMock(return_value=None)
        r = client_messages.post(
            f"/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": "Hi"},
        )
    assert r.status_code == 404


def test_add_reaction_forbidden_403(client_messages):
    """POST /v1/messages/{id}/reactions — 403 если беседа чужая."""
    from datetime import datetime, timezone
    msg_id = uuid4()
    conv_id = uuid4()
    mock_msg = MagicMock()
    mock_msg.id = msg_id
    mock_msg.conversation_id = conv_id
    mock_conv = MagicMock()
    mock_conv.user_id = "other-user"
    with patch("src.api.v1.routes.messages.MessageRepository") as MRepo:
        with patch("src.api.v1.routes.messages.ConversationRepository") as CRepo:
            MRepo.return_value.get_by_id = AsyncMock(return_value=mock_msg)
            CRepo.return_value.get_by_id = AsyncMock(return_value=mock_conv)
            r = client_messages.post(
                f"/v1/messages/{msg_id}/reactions",
                json={"reaction_type": "like"},
            )
    assert r.status_code == 403


def test_create_message_success(client_messages):
    """POST /v1/conversations/{id}/messages — 201 при создании сообщения."""
    from datetime import datetime, timezone
    conv_id = uuid4()
    mock_conv = MagicMock()
    mock_conv.user_id = "user-1"
    mock_msg = MagicMock()
    mock_msg.id = uuid4()
    mock_msg.conversation_id = conv_id
    mock_msg.user_id = "user-1"
    mock_msg.role = "user"
    mock_msg.content = "Hello"
    mock_msg.meta_data = None
    mock_msg.created_at = datetime.now(timezone.utc)
    mock_msg.updated_at = datetime.now(timezone.utc)
    with patch("src.api.v1.routes.messages.ConversationRepository") as ConvRepo:
        with patch("src.api.v1.routes.messages.MessageRepository") as MsgRepo:
            ConvRepo.return_value.get_by_id = AsyncMock(return_value=mock_conv)
            MsgRepo.return_value.create = AsyncMock(return_value=mock_msg)
            r = client_messages.post(
                f"/v1/conversations/{conv_id}/messages",
                json={"role": "user", "content": "Hello"},
            )
    assert r.status_code == 201
    assert "content" in r.json() or "id" in r.json()
