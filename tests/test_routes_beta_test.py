"""Тесты POST /v1/beta-test и Telegram webhook."""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_beta_signup_success_returns_201(client: TestClient):
    """Успешная заявка — 201 и id."""
    with patch("src.api.v1.routes.beta_test.telegram_service") as tg:
        tg.notify_beta_signup = AsyncMock(return_value=True)
        tg.notify_admin_beta_signup = AsyncMock()
        r = client.post(
            "/v1/beta-test",
            json={"telegram": "@testuser", "email": "user@example.com"},
        )
    assert r.status_code == 201
    data = r.json()
    assert data["success"] is True
    assert isinstance(data["id"], str) and len(data["id"]) > 0
    assert data["telegram_notified"] is True
    tg.notify_admin_beta_signup.assert_awaited_once()


def test_beta_signup_without_telegram_chat_returns_notified_false(client: TestClient):
    with patch("src.api.v1.routes.beta_test.telegram_service") as tg:
        tg.notify_beta_signup = AsyncMock(return_value=False)
        tg.notify_admin_beta_signup = AsyncMock()
        r = client.post(
            "/v1/beta-test",
            json={"telegram": "@testuser", "email": "user@example.com"},
        )
    assert r.status_code == 201
    assert r.json()["telegram_notified"] is False


def test_beta_signup_validation_invalid_email_422(client: TestClient):
    """Невалидный email — 422."""
    r = client.post(
        "/v1/beta-test",
        json={"telegram": "@u", "email": "not-an-email"},
    )
    assert r.status_code == 422


def test_telegram_webhook_start_ok(client: TestClient):
    with patch("src.api.v1.routes.telegram_webhook.telegram_service") as tg:
        tg.handle_webhook_update = AsyncMock()
        r = client.post(
            "/v1/telegram/webhook",
            json={
                "message": {
                    "text": "/start",
                    "chat": {"id": 12345, "type": "private"},
                    "from": {"id": 12345, "username": "testuser"},
                }
            },
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    tg.handle_webhook_update.assert_awaited_once()


def test_telegram_webhook_beta_command_ok(client: TestClient):
    with patch("src.api.v1.routes.telegram_webhook.telegram_service") as tg:
        tg.handle_webhook_update = AsyncMock()
        r = client.post(
            "/v1/telegram/webhook",
            json={
                "message": {
                    "text": "/beta",
                    "chat": {"id": 999, "type": "private"},
                    "from": {"id": 999, "username": "admin"},
                }
            },
        )
    assert r.status_code == 200
    tg.handle_webhook_update.assert_awaited_once()
