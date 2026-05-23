"""Тесты RS256 JWT для сессий."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.core.jwt_auth import (
    CLAIM_TOKEN_USE,
    MAX_JWT_STRING_LENGTH,
    TOKEN_USE_SESSION,
    decode_session_jwt,
    encode_session_jwt,
    looks_like_jwt,
    normalize_pem,
    tokens_equal_constant_time,
)


def test_looks_like_jwt():
    assert looks_like_jwt("a.b.c") is True
    assert looks_like_jwt("opaque") is False
    assert looks_like_jwt("a" * (MAX_JWT_STRING_LENGTH + 1)) is False


def test_normalize_pem_literal_newlines():
    one_line = "-----BEGIN X-----\\nMIIB\\n-----END X-----"
    assert "\n" in normalize_pem(one_line)
    assert "\\n" not in normalize_pem(one_line)
    
    quoted_line = '"-----BEGIN X-----\\nMIIB\\n-----END X-----"'
    assert "\n" in normalize_pem(quoted_line)
    assert '"' not in normalize_pem(quoted_line)


def test_encode_decode_roundtrip(test_jwt_keys):
    """Подпись и проверка RS256 (ключи из фикстуры conftest)."""
    priv, pub, issuer = test_jwt_keys
    exp = datetime.now(timezone.utc) + timedelta(days=1)
    tok = encode_session_jwt(
        priv,
        session_id="sid-1",
        user_id="user-1",
        expires_at=exp,
        issuer=issuer,
    )
    assert looks_like_jwt(tok)
    claims = decode_session_jwt(pub, tok, issuer=issuer)
    assert claims["sub"] == "user-1"
    assert claims["sid"] == "sid-1"
    assert claims["iss"] == issuer
    assert claims.get(CLAIM_TOKEN_USE) == TOKEN_USE_SESSION


def test_decode_rejects_wrong_token_use(test_jwt_keys):
    priv, pub, issuer = test_jwt_keys
    exp = datetime.now(timezone.utc) + timedelta(days=1)
    payload = {
        "sub": "u",
        "sid": "s",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(exp.timestamp()),
        "iss": issuer,
        CLAIM_TOKEN_USE: "refresh",
    }
    bad = jwt.encode(payload, normalize_pem(priv), algorithm="RS256")
    with pytest.raises(jwt.PyJWTError):
        decode_session_jwt(pub, bad, issuer=issuer)


def test_decode_token_too_long(test_jwt_keys):
    _, pub, issuer = test_jwt_keys
    long_tok = "x." + "y" * MAX_JWT_STRING_LENGTH + ".z"
    assert len(long_tok) > MAX_JWT_STRING_LENGTH
    with pytest.raises(jwt.PyJWTError):
        decode_session_jwt(pub, long_tok, issuer=issuer)


def test_tokens_equal_constant_time():
    assert tokens_equal_constant_time("a", "a") is True
    assert tokens_equal_constant_time("a", "b") is False
    assert tokens_equal_constant_time("ab", "a") is False


def test_audience_roundtrip(test_jwt_keys):
    priv, pub, issuer = test_jwt_keys
    aud = "delez-clients"
    exp = datetime.now(timezone.utc) + timedelta(days=1)
    tok = encode_session_jwt(
        priv,
        session_id="sid-aud",
        user_id="user-aud",
        expires_at=exp,
        issuer=issuer,
        audience=aud,
    )
    claims = decode_session_jwt(pub, tok, issuer=issuer, audience=aud)
    assert claims["aud"] == aud
