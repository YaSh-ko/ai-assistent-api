"""Тесты исключений core.exceptions (покрытие модуля)."""
import pytest
from fastapi import status

from src.core.exceptions import (
    AuthException,
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
    InvalidTokenException,
    SessionExpiredException,
    UnauthorizedException,
    BadRequestException,
)


def test_auth_exception_status():
    e = AuthException("msg")
    assert e.status_code == status.HTTP_401_UNAUTHORIZED
    assert e.detail == "msg"


def test_invalid_credentials_exception():
    e = InvalidCredentialsException()
    assert e.status_code == status.HTTP_401_UNAUTHORIZED
    e2 = InvalidCredentialsException("custom")
    assert e2.detail == "custom"


def test_user_already_exists_exception():
    e = UserAlreadyExistsException()
    assert e.status_code == status.HTTP_409_CONFLICT


def test_user_not_found_exception():
    e = UserNotFoundException()
    assert e.status_code == status.HTTP_404_NOT_FOUND


def test_invalid_token_exception():
    e = InvalidTokenException()
    assert e.status_code == status.HTTP_401_UNAUTHORIZED


def test_session_expired_exception():
    e = SessionExpiredException()
    assert e.status_code == status.HTTP_401_UNAUTHORIZED


def test_unauthorized_exception():
    e = UnauthorizedException()
    assert e.status_code == status.HTTP_401_UNAUTHORIZED


def test_bad_request_exception():
    e = BadRequestException("invalid")
    assert e.status_code == status.HTTP_400_BAD_REQUEST
    assert e.detail == "invalid"
