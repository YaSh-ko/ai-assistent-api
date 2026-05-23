"""Тесты эндпоинтов auth (с моками)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.api.v1.schemas.auth import SignInRequest, SignUpRequest, ResetPasswordRequest
from src.core.exceptions import (
    UserAlreadyExistsException,
    InvalidCredentialsException,
    InvalidTokenException,
    BadRequestException,
    JwtConfigurationException,
)
from src.core.rate_limit import reset_limiters_for_tests


@pytest.fixture(autouse=True)
def _reset_rate_limiters_before_each_test():
    reset_limiters_for_tests()
    yield
    reset_limiters_for_tests()


def test_sign_up_success(client: TestClient):
    """Успешная регистрация — 201 и сообщение про почту."""
    body = dict(zip(SignUpRequest.model_fields, ["new@example.com", "longenough", "Test"]))
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.sign_up = AsyncMock(return_value=None)
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/sign-up/email", json=body)
    assert r.status_code == 201
    data = r.json()
    assert data.get("success") is True
    assert "почту" in data.get("message", "")


def test_sign_up_duplicate_email_returns_409(client: TestClient):
    """Повторная регистрация того же email — 409."""
    body = dict(zip(SignUpRequest.model_fields, ["existing@example.com", "longenough", None]))
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.sign_up = AsyncMock(side_effect=UserAlreadyExistsException())
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/sign-up/email", json=body)
    assert r.status_code == 409


def test_sign_in_success_returns_200_and_session(client: TestClient):
    """Успешный вход — 200, user/session в ответе и cookie."""
    from datetime import datetime, timezone, timedelta
    body = {f: ("user@example.com" if f == "email" else "secret6") for f in SignInRequest.model_fields}
    mock_user = MagicMock()
    mock_user.id = "u1"
    mock_user.email = "user@example.com"
    mock_user.name = "Test"
    mock_session = MagicMock()
    mock_session.token = "sess-tok"
    mock_session.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.sign_in = AsyncMock(return_value=(mock_user, mock_session))
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/sign-in/email", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["id"] == "u1"
    assert "session_token" in r.cookies or "Set-Cookie" in r.headers


def test_sign_in_invalid_credentials_returns_401(client: TestClient):
    """Неверный пароль — 401."""
    body = {f: ("user@example.com" if f == "email" else "wrong") for f in SignInRequest.model_fields}
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.sign_in = AsyncMock(side_effect=InvalidCredentialsException())
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/sign-in/email", json=body)
    assert r.status_code == 401


def test_sign_in_jwt_not_configured_returns_503(client: TestClient):
    """
    При отсутствии настроек RS256 create_session поднимает JwtConfigurationException — API отдаёт 503.
    Сервис замокан, имитируем тот же сценарий, что и при реальном вызове create_session без ключей.
    """
    body = {f: ("user@example.com" if f == "email" else "secret6") for f in SignInRequest.model_fields}
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.sign_in = AsyncMock(side_effect=JwtConfigurationException())
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/sign-in/email", json=body)
    assert r.status_code == 503
    data = r.json()
    assert data.get("error") == "JwtConfigurationException"
    assert "message" in data


def test_get_session_no_cookie_returns_401(client: TestClient):
    """get_session без токена — 401."""
    r = client.get("/auth/get-session")
    assert r.status_code == 401


def test_forget_password_returns_200(client: TestClient):
    """forget_password всегда 200 (защита от перебора)."""
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.initiate_password_reset = AsyncMock(return_value=None)
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/forget-password", json={"email": "user@example.com"})
    assert r.status_code == 200
    assert r.json().get("success") is True


def test_reset_password_invalid_token_returns_401(client: TestClient):
    """reset_password с неверным токеном — 401."""
    body = dict(zip(ResetPasswordRequest.model_fields, ["bad-token", "newpass6"]))
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.reset_password = AsyncMock(side_effect=InvalidTokenException())
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/reset-password", json=body)
    assert r.status_code == 401


def test_resend_verification_returns_200(client: TestClient):
    """resend_verification — 200 и success."""
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.resend_verification_email = AsyncMock(return_value=None)
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/resend-verification", json={"email": "user@example.com"})
    assert r.status_code == 200
    assert r.json().get("success") is True


def test_verify_email_success(client: TestClient):
    """verify_email при валидном токене — 200."""
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.verify_email = AsyncMock(return_value=True)
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/verify-email", json={"token": "valid-token"})
    assert r.status_code == 200
    assert r.json().get("success") is True


def test_verify_email_invalid_returns_401(client: TestClient):
    """verify_email при неверном токене — 401."""
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.verify_email = AsyncMock(return_value=False)
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/verify-email", json={"token": "bad-token"})
    assert r.status_code == 401


def test_sign_up_validation_error_returns_422(client: TestClient):
    """sign_up с невалидным телом — 422."""
    r = client.post("/auth/sign-up/email", json={"email": "not-an-email", "name": "X"})
    assert r.status_code == 422


def test_sign_out_success_returns_200(client: TestClient):
    """sign_out с токеном — 200."""
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.sign_out = AsyncMock(return_value=True)
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/sign-out", headers={"Authorization": "Bearer sess-tok"})
    assert r.status_code == 200


def test_sign_up_bad_request_returns_400(client: TestClient):
    """sign_up при BadRequestException — 400."""
    body = dict(zip(SignUpRequest.model_fields, ["new@x.com", "longenough", "Name"]))
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.sign_up = AsyncMock(side_effect=BadRequestException("Email required"))
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/sign-up/email", json=body)
    assert r.status_code == 400


def test_sign_up_sqlalchemy_error_raises(client: TestClient):
    """sign_up при SQLAlchemyError пробрасывает (обработчик main вернёт 500)."""
    body = dict(zip(SignUpRequest.model_fields, ["new@x.com", "longenough", "Name"]))
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.sign_up = AsyncMock(side_effect=SQLAlchemyError("db error"))
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/sign-up/email", json=body)
    assert r.status_code == 500


def test_sign_in_sqlalchemy_error_raises(client: TestClient):
    """sign_in при SQLAlchemyError пробрасывает (500)."""
    body = {f: ("u@x.com" if f == "email" else "secret6") for f in SignInRequest.model_fields}
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.sign_in = AsyncMock(side_effect=SQLAlchemyError("db error"))
        AuthServiceCls.return_value = auth_svc
        r = client.post("/auth/sign-in/email", json=body)
    assert r.status_code == 500


def test_get_session_success_with_cookie(client: TestClient):
    """get_session с валидной cookie — 200 и user/session."""
    from datetime import datetime, timezone, timedelta
    mock_user = MagicMock()
    mock_user.id = "u1"
    mock_user.email = "u@x.com"
    mock_user.name = "User"
    mock_user.createdAt = datetime.now(timezone.utc)
    mock_session = MagicMock()
    mock_session.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    with patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        auth_svc = MagicMock()
        auth_svc.get_current_session = AsyncMock(return_value=(mock_user, mock_session))
        AuthServiceCls.return_value = auth_svc
        r = client.get("/auth/get-session", cookies={"session_token": "valid-tok"})
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["id"] == "u1"


def test_sign_up_same_ip_blocked_by_signup_ip_limit(client: TestClient):
    """Повторная регистрация с одного IP блокируется (429)."""
    body1 = dict(zip(SignUpRequest.model_fields, ["first@example.com", "longenough", "A"]))
    body2 = dict(zip(SignUpRequest.model_fields, ["second@example.com", "longenough", "B"]))
    reset_limiters_for_tests()
    with patch("src.api.v1.routes.auth.settings") as mock_settings, \
         patch("src.api.v1.routes.auth.AuthService") as AuthServiceCls:
        mock_settings.SIGNUP_IP_LIMIT_ENABLED = True
        mock_settings.SIGNUP_IP_MAX_REGISTRATIONS = 1
        mock_settings.SIGNUP_IP_WINDOW_SECONDS = 3600
        auth_svc = MagicMock()
        auth_svc.sign_up = AsyncMock(return_value=None)
        AuthServiceCls.return_value = auth_svc

        r1 = client.post("/auth/sign-up/email", json=body1)
        r2 = client.post("/auth/sign-up/email", json=body2)

    assert r1.status_code == 201
    assert r2.status_code == 429


def test_global_rate_limit_returns_429(client: TestClient):
    """Глобальный лимит запросов возвращает 429 при превышении."""
    reset_limiters_for_tests()
    with patch("src.main.settings") as main_settings:
        main_settings.RATE_LIMIT_ENABLED = True
        main_settings.RATE_LIMIT_WINDOW_SECONDS = 60
        main_settings.RATE_LIMIT_MAX_REQUESTS = 1
        main_settings.RATE_LIMIT_EXCLUDE_PATHS = "/docs,/redoc,/openapi.json,/v1/health"

        r1 = client.get("/auth/get-session")
        r2 = client.get("/auth/get-session")

    assert r1.status_code == 401
    assert r2.status_code == 429
