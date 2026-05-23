# tests/unit/test_auth_service.py
"""Unit-тесты AuthService (хэш, верификация пароля, токены, сессии)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.auth_service import AuthService
from src.core.exceptions import (
    BadRequestException,
    InvalidCredentialsException,
    InvalidTokenException,
    UnauthorizedException,
    UserAlreadyExistsException,
    SessionExpiredException,
    JwtConfigurationException,
)


# --- Статические методы (без БД) ---

def test_hash_password_returns_salt_and_hash():
    h = AuthService.hash_password("secret123")
    assert ":" in h
    parts = h.split(":", 1)
    assert len(parts[0]) == 32  # salt hex 16 bytes
    assert len(parts[1]) == 64  # sha256 hex


def test_verify_password_true_when_match():
    h = AuthService.hash_password("mypass")
    assert AuthService.verify_password("mypass", h) is True


def test_verify_password_false_when_wrong():
    h = AuthService.hash_password("mypass")
    assert AuthService.verify_password("wrong", h) is False


def test_verify_password_false_empty_password():
    h = AuthService.hash_password("x")
    assert AuthService.verify_password("", h) is False


def test_verify_password_false_empty_stored():
    assert AuthService.verify_password("x", "") is False


def test_verify_password_false_invalid_format():
    assert AuthService.verify_password("x", "noseparator") is False


def test_verify_password_handles_attribute_error():
    """verify_password при AttributeError в try возвращает False (стр. 64-65)."""
    class BadAdd:
        def __add__(self, other):
            return 123  # int has no .encode()
    assert AuthService.verify_password(BadAdd(), "x:y") is False


def test_generate_session_token_non_empty():
    t = AuthService.generate_session_token()
    assert isinstance(t, str) and len(t) > 0


def test_generate_reset_token_non_empty():
    t = AuthService.generate_reset_token()
    assert isinstance(t, str) and len(t) > 0


def test_generate_id_uuid_format():
    uid = AuthService.generate_id()
    assert isinstance(uid, str) and len(uid) == 36 and uid.count("-") == 4


# --- С моком БД ---

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_get_user_by_email_returns_user(mock_db):
    from common.database.models import User
    user = User(id="u1", email="a@b.com", name="A", emailVerified=True)
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
    svc = AuthService(mock_db)
    out = await svc.get_user_by_email("a@b.com")
    assert out is user


@pytest.mark.asyncio
async def test_get_user_by_email_returns_none(mock_db):
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    svc = AuthService(mock_db)
    out = await svc.get_user_by_email("missing@b.com")
    assert out is None


@pytest.mark.asyncio
async def test_get_user_by_id_returns_user(mock_db):
    from common.database.models import User
    user = User(id="u1", email="a@b.com", name="A", emailVerified=True)
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
    svc = AuthService(mock_db)
    out = await svc.get_user_by_id("u1")
    assert out is user


@pytest.mark.asyncio
async def test_validate_session_raises_when_no_session(mock_db):
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    svc = AuthService(mock_db)
    with pytest.raises(UnauthorizedException):
        await svc.validate_session("bad-token")


@pytest.mark.asyncio
async def test_validate_session_returns_user_and_session(mock_db):
    from common.database.models import User, Session
    from datetime import datetime, timezone, timedelta
    user = User(id="u1", email="a@b.com", name="A", emailVerified=True)
    session = Session(id="s1", user_id="u1", token="tok", expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    mock_db.execute = AsyncMock()
    def execute_side_effect(*args, **kwargs):
        # first call: get_session_by_token; second: get_user_by_id
        if execute_side_effect.call_count == 1:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=session))
        return MagicMock(scalar_one_or_none=MagicMock(return_value=user))
    execute_side_effect.call_count = 0
    def run_execute(*a, **k):
        execute_side_effect.call_count += 1
        if execute_side_effect.call_count == 1:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=session))
        return MagicMock(scalar_one_or_none=MagicMock(return_value=user))
    mock_db.execute.side_effect = run_execute
    svc = AuthService(mock_db)
    u, s = await svc.validate_session("tok")
    assert u is user and s is session


@pytest.mark.asyncio
async def test_create_user_raises_empty_email(mock_db):
    svc = AuthService(mock_db)
    with pytest.raises(BadRequestException):
        await svc.create_user("", "password123")


@pytest.mark.asyncio
async def test_create_user_raises_short_password(mock_db):
    svc = AuthService(mock_db)
    with pytest.raises(BadRequestException):
        await svc.create_user("a@b.com", "12345")


@pytest.mark.asyncio
async def test_create_user_raises_when_user_exists(mock_db):
    from common.database.models import User
    existing = User(id="u1", email="a@b.com", name="A", emailVerified=False)
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing)))
    svc = AuthService(mock_db)
    with pytest.raises(UserAlreadyExistsException):
        await svc.create_user("a@b.com", "password123")


@pytest.mark.asyncio
async def test_sign_in_raises_empty_email(mock_db):
    svc = AuthService(mock_db)
    with pytest.raises(BadRequestException):
        await svc.sign_in("", "pass")


@pytest.mark.asyncio
async def test_sign_in_raises_empty_password(mock_db):
    svc = AuthService(mock_db)
    with pytest.raises(BadRequestException):
        await svc.sign_in("a@b.com", "")


@pytest.mark.asyncio
async def test_sign_in_raises_user_not_found(mock_db):
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    svc = AuthService(mock_db)
    with pytest.raises(InvalidCredentialsException):
        await svc.sign_in("missing@b.com", "password")


@pytest.mark.asyncio
async def test_sign_out_returns_true_when_session_deleted(mock_db):
    from common.database.models import Session
    session = Session(id="s1", user_id="u1", token="t", expires_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=session))
    svc = AuthService(mock_db)
    result = await svc.sign_out("t")
    assert result is True


@pytest.mark.asyncio
async def test_get_current_session_delegates_to_validate_session(mock_db):
    from common.database.models import User, Session
    from datetime import datetime, timezone, timedelta
    user = User(id="u1", email="a@b.com", name="A", emailVerified=True)
    session = Session(id="s1", user_id="u1", token="tok", expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    call_count = [0]
    def run_execute(*a, **k):
        call_count[0] += 1
        if call_count[0] == 1:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=session))
        return MagicMock(scalar_one_or_none=MagicMock(return_value=user))
    mock_db.execute.side_effect = run_execute
    svc = AuthService(mock_db)
    u, s = await svc.get_current_session("tok")
    assert u is user and s is session


@pytest.mark.asyncio
async def test_initiate_password_reset_returns_none_when_user_missing(mock_db):
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    svc = AuthService(mock_db)
    result = await svc.initiate_password_reset("missing@b.com")
    assert result is None


@pytest.mark.asyncio
async def test_reset_password_raises_empty_token(mock_db):
    svc = AuthService(mock_db)
    with pytest.raises(BadRequestException):
        await svc.reset_password("", "newpass123")


@pytest.mark.asyncio
async def test_reset_password_raises_short_new_password(mock_db):
    svc = AuthService(mock_db)
    with pytest.raises(BadRequestException):
        await svc.reset_password("token", "short")


@pytest.mark.asyncio
async def test_reset_password_raises_invalid_token(mock_db):
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    svc = AuthService(mock_db)
    with pytest.raises(InvalidTokenException):
        await svc.reset_password("bad-token", "newpass123")


@pytest.mark.asyncio
async def test_create_session_raises_empty_user_id(mock_db):
    svc = AuthService(mock_db)
    with pytest.raises(BadRequestException):
        await svc.create_session("")


@pytest.mark.asyncio
async def test_create_session_returns_session(mock_db):
    from common.database.models import Session
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    svc = AuthService(mock_db)
    session = await svc.create_session("user-1", ip_address="127.0.0.1", user_agent="Test")
    assert session is not None
    assert session.user_id == "user-1"
    assert session.token is not None
    assert session.ip_address == "127.0.0.1"
    assert session.user_agent == "Test"


@pytest.mark.asyncio
async def test_create_session_truncates_long_ip(mock_db):
    from common.database.models import Session
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    svc = AuthService(mock_db)
    long_ip = "1.2.3.4." + "x" * 50
    session = await svc.create_session("u", ip_address=long_ip)
    assert session.ip_address is not None
    assert len(session.ip_address) <= 45


@pytest.mark.asyncio
async def test_create_user_success(mock_db):
    """create_user создаёт User и Account при отсутствии пользователя."""
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_db.refresh = AsyncMock()
    svc = AuthService(mock_db)
    user = await svc.create_user("new@test.com", "longenough", "Display")
    assert user.email == "new@test.com"
    assert user.name == "Display"
    assert mock_db.add.call_count >= 2


@pytest.mark.asyncio
async def test_validate_session_raises_when_expired(mock_db):
    """validate_session вызывает SessionExpiredException при истёкшей сессии."""
    from common.database.models import Session
    from datetime import datetime, timezone, timedelta
    expired_session = Session(
        id="s1", user_id="u1", token="t",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    mock_db.execute = AsyncMock()
    call_count = [0]
    def run_execute(*a, **k):
        call_count[0] += 1
        if call_count[0] == 1:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=expired_session))
        return MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = run_execute
    svc = AuthService(mock_db)
    with pytest.raises(SessionExpiredException):
        await svc.validate_session("t")


@pytest.mark.asyncio
async def test_sign_in_success_returns_user_and_session(mock_db):
    """sign_in при верном пароле и подтверждённой почте возвращает user и session."""
    from common.database.models import User, Account, Session
    from datetime import datetime, timezone, timedelta
    user = User(id="u1", email="a@b.com", name="A", emailVerified=True)
    account = Account(id="acc1", user_id="u1", provider_id="credential", password=AuthService.hash_password("secret6"))
    session = Session(id="s1", user_id="u1", token="tok", expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    mock_db.execute = AsyncMock()
    call_count = [0]
    def run_execute(*a, **k):
        call_count[0] += 1
        if call_count[0] == 1:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=user))
        if call_count[0] == 2:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=account))
        return MagicMock(scalar_one_or_none=MagicMock(return_value=session))
    mock_db.execute.side_effect = run_execute
    mock_db.add = MagicMock()
    mock_db.refresh = AsyncMock()
    svc = AuthService(mock_db)
    u, s = await svc.sign_in("a@b.com", "secret6")
    assert u is user
    assert s.user_id == "u1"


@pytest.mark.asyncio
async def test_sign_in_raises_when_email_not_verified(mock_db):
    """sign_in при неподтверждённой почте — BadRequestException."""
    from common.database.models import User, Account
    user = User(id="u1", email="a@b.com", name="A", emailVerified=False)
    account = Account(id="acc1", user_id="u1", provider_id="credential", password=AuthService.hash_password("secret6"))
    results = [user, account]
    def run_execute(*a, **k):
        r = MagicMock()
        r.scalar_one_or_none = MagicMock(return_value=results.pop(0) if results else None)
        return r
    mock_db.execute = AsyncMock(side_effect=run_execute)
    mock_db.add = MagicMock()
    mock_db.refresh = AsyncMock()
    svc = AuthService(mock_db)
    with pytest.raises(BadRequestException):
        await svc.sign_in("a@b.com", "secret6")


@pytest.mark.asyncio
async def test_get_session_by_token_returns_none(mock_db):
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    svc = AuthService(mock_db)
    out = await svc.get_session_by_token("unknown")
    assert out is None


@pytest.mark.asyncio
async def test_delete_session_returns_false_when_no_session(mock_db):
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    svc = AuthService(mock_db)
    out = await svc.delete_session("unknown")
    assert out is False


@pytest.mark.asyncio
async def test_resend_verification_email_returns_token_when_user_not_verified(mock_db):
    """resend_verification_email при неподтверждённом пользователе отправляет письмо и возвращает токен."""
    from common.database.models import User, Account
    user = User(id="u1", email="a@b.com", name="A", emailVerified=False)
    account = MagicMock()
    account.user_id = "u1"
    results = [user, account]
    def run_execute(*a, **k):
        r = MagicMock()
        r.scalar_one_or_none = MagicMock(return_value=results.pop(0) if results else None)
        return r
    mock_db.execute = AsyncMock(side_effect=run_execute)
    mock_em = MagicMock()
    mock_em.send_verification_email = AsyncMock(return_value=None)
    with patch("src.services.email_service.email_service", mock_em):
        svc = AuthService(mock_db)
        token = await svc.resend_verification_email("a@b.com")
    assert token is not None


@pytest.mark.asyncio
async def test_verify_email_returns_true_when_valid_token(mock_db):
    from common.database.models import User, Account
    from datetime import datetime, timezone, timedelta
    user = User(id="u1", email="a@b.com", name="A", emailVerified=False)
    account = Account(id="acc1", user_id="u1", provider_id="credential")
    account.access_token = "valid-token"
    account.access_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    results = [account, user]
    def run_execute(*a, **k):
        r = MagicMock()
        r.scalar_one_or_none = MagicMock(return_value=results.pop(0) if results else None)
        return r
    mock_db.execute = AsyncMock(side_effect=run_execute)
    mock_db.commit = AsyncMock()
    svc = AuthService(mock_db)
    result = await svc.verify_email("valid-token")
    assert result is True


@pytest.mark.asyncio
async def test_verify_email_returns_false_when_token_not_found(mock_db):
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    svc = AuthService(mock_db)
    result = await svc.verify_email("bad-token")
    assert result is False


@pytest.mark.asyncio
async def test_reset_password_success(mock_db):
    from common.database.models import Account
    from datetime import datetime, timezone, timedelta
    account = Account(id="acc1", user_id="u1", provider_id="credential")
    account.access_token = "reset-tok"
    account.access_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    mock_db.execute = AsyncMock()
    call_count = [0]
    def run_execute(*a, **k):
        call_count[0] += 1
        if call_count[0] == 1:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=account))
        return MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = run_execute
    svc = AuthService(mock_db)
    result = await svc.reset_password("reset-tok", "newpass6")
    assert result is True


@pytest.mark.asyncio
async def test_sign_up_calls_create_user_and_sends_verification(mock_db):
    """sign_up создаёт пользователя и отправляет письмо (мок email)."""
    from common.database.models import User, Account
    mock_user = User(id="u1", email="new@test.com", name="Display", emailVerified=False)
    account = MagicMock()
    account.user_id = "u1"
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=account))
    mock_db.refresh = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_em = MagicMock()
    mock_em.send_verification_email = AsyncMock(return_value=None)
    with patch("src.services.email_service.email_service", mock_em):
        with patch.object(AuthService, "create_user", new_callable=AsyncMock, return_value=mock_user):
            svc = AuthService(mock_db)
            result = await svc.sign_up("new@test.com", "longenough", "Display")
    assert result is mock_user


@pytest.mark.asyncio
async def test_initiate_password_reset_sends_email_when_user_exists(mock_db):
    """initiate_password_reset при найденном пользователе сохраняет токен и отправляет письмо."""
    from common.database.models import User
    user = User(id="u1", email="a@b.com", name="A", emailVerified=True)
    account = MagicMock()
    account.user_id = "u1"
    results = [user, account]
    def run_execute(*a, **k):
        r = MagicMock()
        r.scalar_one_or_none = MagicMock(return_value=results.pop(0) if results else None)
        return r
    mock_db.execute = AsyncMock(side_effect=run_execute)
    mock_db.commit = AsyncMock()
    mock_em = MagicMock()
    mock_em.send_password_reset_email = AsyncMock(return_value=True)
    with patch("src.services.email_service.email_service", mock_em):
        svc = AuthService(mock_db)
        token = await svc.initiate_password_reset("a@b.com")
    assert token is not None


@pytest.mark.asyncio
async def test_create_user_raises_user_exists_on_integrity_error(mock_db):
    """create_user при IntegrityError с unique/duplicate пробрасывает UserAlreadyExistsException."""
    from sqlalchemy.exc import IntegrityError
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_db.flush = AsyncMock(side_effect=IntegrityError("stmt", "params", "unique constraint"))
    mock_db.rollback = AsyncMock()
    svc = AuthService(mock_db)
    with pytest.raises(UserAlreadyExistsException):
        await svc.create_user("new@test.com", "longenough", "Name")


@pytest.mark.asyncio
async def test_validate_session_raises_when_user_not_found(mock_db):
    """validate_session при отсутствии user после сессии — UnauthorizedException."""
    from common.database.models import Session
    from datetime import datetime, timezone, timedelta
    session = Session(id="s1", user_id="u1", token="t", expires_at=datetime.now(timezone.utc) + timedelta(days=1))
    call_count = [0]
    def run_execute(*a, **k):
        call_count[0] += 1
        if call_count[0] == 1:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=session))
        return MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    mock_db.execute.side_effect = run_execute
    svc = AuthService(mock_db)
    with pytest.raises(UnauthorizedException):
        await svc.validate_session("t")


@pytest.mark.asyncio
async def test_create_session_sqlalchemy_error_raises(mock_db):
    """create_session при SQLAlchemyError пробрасывает исключение."""
    from sqlalchemy.exc import SQLAlchemyError
    mock_db.commit = AsyncMock(side_effect=SQLAlchemyError("db error"))
    mock_db.rollback = AsyncMock()
    svc = AuthService(mock_db)
    with pytest.raises(SQLAlchemyError):
        await svc.create_session("user-1")


@pytest.mark.asyncio
async def test_create_session_raises_when_jwt_keys_missing(mock_db):
    """Без PEM-ключей RS256 create_session не создаёт RuntimeError, а JwtConfigurationException (503)."""
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    svc = AuthService(mock_db)
    with patch("src.services.auth_service.settings") as mock_settings:
        mock_settings.JWT_PRIVATE_KEY_PEM = None
        mock_settings.JWT_PUBLIC_KEY_PEM = None
        with pytest.raises(JwtConfigurationException) as exc_info:
            await svc.create_session("user-1")
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_validate_session_jwt_like_without_public_key(mock_db):
    """Строка вида JWT без настроенного публичного ключа не уходит в opaque-ветку."""
    svc = AuthService(mock_db)
    jwt_shaped = "aaa.bbb.ccc"
    with patch("src.services.auth_service.settings") as mock_settings:
        mock_settings.JWT_PUBLIC_KEY_PEM = None
        with pytest.raises(UnauthorizedException):
            await svc.validate_session(jwt_shaped)


@pytest.mark.asyncio
async def test_delete_session_fallback_by_sid_when_token_lookup_misses(mock_db, test_jwt_keys):
    """
    Если по полному token строка в БД не найдена, но JWT валиден и sid указывает на строку
    с тем же token (constant-time), сессия удаляется (резервный путь после get_session_by_token).
    """
    from datetime import datetime, timezone, timedelta

    from common.database.models import Session

    from src.core.jwt_auth import encode_session_jwt

    priv, _pub, issuer = test_jwt_keys
    sid = "00000000-0000-4000-8000-00000000fb01"
    uid = "user-fallback-del"
    exp = datetime.now(timezone.utc) + timedelta(days=1)
    token = encode_session_jwt(
        priv,
        session_id=sid,
        user_id=uid,
        expires_at=exp,
        issuer=issuer,
    )
    row = Session(id=sid, user_id=uid, token=token, expires_at=exp)
    call_count = [0]

    def run_execute(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        if call_count[0] == 2:
            return MagicMock(scalar_one_or_none=MagicMock(return_value=row))
        return MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    mock_db.execute = AsyncMock(side_effect=run_execute)
    svc = AuthService(mock_db)
    assert await svc.delete_session(token) is True
    assert mock_db.commit.call_count >= 1


@pytest.mark.asyncio
async def test_reset_password_raises_when_token_expired(mock_db):
    """reset_password при истёкшем access_token_expires_at — InvalidTokenException."""
    from common.database.models import Account
    from datetime import datetime, timezone, timedelta
    account = Account(id="a1", user_id="u1", provider_id="credential")
    account.access_token = "tok"
    account.access_token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=account)))
    mock_db.commit = AsyncMock()
    svc = AuthService(mock_db)
    with pytest.raises(InvalidTokenException):
        await svc.reset_password("tok", "newpass6")


@pytest.mark.asyncio
async def test_resend_verification_email_returns_none_when_user_verified(mock_db):
    """resend_verification_email при уже подтверждённом пользователе возвращает None."""
    from common.database.models import User
    user = User(id="u1", email="a@b.com", name="A", emailVerified=True)
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=user)))
    svc = AuthService(mock_db)
    result = await svc.resend_verification_email("a@b.com")
    assert result is None
