"""
JWT access tokens для сессий: алгоритм RS256 (RSA + SHA-256).

Безопасность:
- Явно указан список алгоритмов (только RS256), без «algorithm confusion».
- Ограничение длины входной строки до декодирования (защита от DoS).
- Сравнение токенов на стороне приложения — через secrets.compare_digest (см. tokens_equal_constant_time).
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

import jwt

JWT_ALGORITHM = "RS256"
# Практический максимум для RS256 JWT (~2–4 KB); запас для заголовков/claims
MAX_JWT_STRING_LENGTH = 16384

# Тип токена: отличает сессионный JWT от будущих refresh и т.д.
CLAIM_TOKEN_USE = "token_use"
TOKEN_USE_SESSION = "session"


def normalize_pem(pem: str) -> str:
    """
    Приводит PEM из .env к нормальному виду (часто передают \\n вместо перевода строки).
    Удаляет случайные кавычки и слэши из переменных окружения GitLab CI.
    """
    s = pem.strip()
    
    # В валидном PEM (Base64 + заголовки) никогда не бывает кавычек
    s = s.replace('"', '').replace("'", "")
    
    # Обрабатываем возможные экранирования переносов строк (\\n или \n)
    s = s.replace("\\\\n", "\n")
    s = s.replace("\\n", "\n")
    s = s.replace("\\\\r", "")
    s = s.replace("\\r", "")

    # Удаляем оставшиеся висячие бэк-слэши (например, от экранированной кавычки \")
    s = s.replace("\\", "")
    
    return s.strip()


def looks_like_jwt(token: str) -> bool:
    """
    Эвристика: три сегмента base64url через точку.
    Не гарантирует валидный JWT, но отсекает явный мусор.
    """
    if not token or len(token) > MAX_JWT_STRING_LENGTH:
        return False
    if token.count(".") != 2:
        return False
    # base64url: A-Za-z0-9-_
    if not re.match(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$", token):
        return False
    return True


def encode_session_jwt(
    private_key_pem: str,
    *,
    session_id: str,
    user_id: str,
    expires_at: datetime,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """Выпускает подписанный JWT для сессии (RS256)."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        CLAIM_TOKEN_USE: TOKEN_USE_SESSION,
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience
    return jwt.encode(
        payload,
        normalize_pem(private_key_pem),
        algorithm=JWT_ALGORITHM,
        headers={"typ": "JWT", "alg": JWT_ALGORITHM},
    )


def decode_session_jwt(
    public_key_pem: str,
    token: str,
    *,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    leeway_seconds: int = 0,
) -> dict[str, Any]:
    """
    Проверяет подпись RS256 и возвращает payload.

    leeway_seconds — допуск по часам между клиентом и сервером (nbf/exp).
    """
    if len(token) > MAX_JWT_STRING_LENGTH:
        raise jwt.InvalidTokenError("Token too long")

    require = ["exp", "iat", "sub", "sid"]
    if issuer:
        require.append("iss")
    if audience:
        require.append("aud")

    kwargs: dict[str, Any] = {
        "algorithms": [JWT_ALGORITHM],
        "options": {
            "require": require,
            "verify_signature": True,
        },
        "leeway": leeway_seconds,
    }
    if issuer:
        kwargs["issuer"] = issuer
    if audience:
        kwargs["audience"] = audience

    claims = jwt.decode(token, normalize_pem(public_key_pem), **kwargs)

    tu = claims.get(CLAIM_TOKEN_USE)
    if tu is not None and tu != TOKEN_USE_SESSION:
        raise jwt.InvalidTokenError("Invalid token_use")

    sub = claims.get("sub")
    sid = claims.get("sid")
    if not isinstance(sub, str) or not isinstance(sid, str) or not sub.strip() or not sid.strip():
        raise jwt.InvalidTokenError("Invalid sub/sid")

    return claims


def tokens_equal_constant_time(a: str, b: str) -> bool:
    """Сравнение строк токенов без утечки по времени (если длины совпадают)."""
    if len(a) != len(b):
        return False
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
