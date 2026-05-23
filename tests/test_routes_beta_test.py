"""Тесты POST /v1/beta-test (заявка на бета-тестирование)."""
from fastapi.testclient import TestClient


def test_beta_signup_success_returns_201(client: TestClient):
    """Успешная заявка — 201 и id."""
    r = client.post(
        "/v1/beta-test",
        json={"telegram": "@testuser", "email": "user@example.com"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["success"] is True
    assert isinstance(data["id"], str) and len(data["id"]) > 0


def test_beta_signup_validation_invalid_email_422(client: TestClient):
    """Невалидный email — 422."""
    r = client.post(
        "/v1/beta-test",
        json={"telegram": "@u", "email": "not-an-email"},
    )
    assert r.status_code == 422
