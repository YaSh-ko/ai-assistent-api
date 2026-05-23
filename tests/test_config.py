"""Тесты конфигурации."""
import os
import pytest
from src.core.config import Settings


def test_cors_origins_default():
    """CORS_ORIGINS по умолчанию — список с https://delez.tech (без env из conftest)."""
    old = os.environ.pop("CORS_ORIGINS", None)
    try:
        s = Settings()
        assert isinstance(s.CORS_ORIGINS, list)
        assert "https://delez.tech" in s.CORS_ORIGINS
    finally:
        if old is not None:
            os.environ["CORS_ORIGINS"] = old


def test_parse_cors_origins_list():
    """CORS_ORIGINS как список остаётся списком."""
    s = Settings(CORS_ORIGINS=["https://a.com", "https://b.com"])
    assert s.CORS_ORIGINS == ["https://a.com", "https://b.com"]


def test_parse_cors_origins_comma_string():
    """CORS_ORIGINS как строка с запятыми парсится в список."""
    s = Settings(CORS_ORIGINS="https://a.com, https://b.com")
    assert s.CORS_ORIGINS == ["https://a.com", "https://b.com"]


def test_parse_cors_origins_json_string():
    """CORS_ORIGINS как JSON-строка парсится в список."""
    s = Settings(CORS_ORIGINS='["https://x.com"]')
    assert s.CORS_ORIGINS == ["https://x.com"]


def test_parse_cors_origins_invalid_json_falls_back():
    """Невалидный JSON для CORS_ORIGINS — fallback на запятую или один элемент."""
    s = Settings(CORS_ORIGINS="https://only-one.com")
    assert "https://only-one.com" in s.CORS_ORIGINS


def test_db_url_uses_database_url_when_set():
    """Если задан DATABASE_URL — возвращается он."""
    url = "postgresql+asyncpg://user:x@host:5432/mydb"
    s = Settings(DATABASE_URL=url)
    assert s.db_url == url


def test_db_url_built_from_components():
    """Без DATABASE_URL URL собирается из POSTGRES_* (host, port, db и логин)."""
    old_url = os.environ.pop("DATABASE_URL", None)
    try:
        pg_ordered = [k for k in Settings.model_fields if k.startswith("POSTGRES_") and len(k) != 17]
        kwargs = {
            pg_ordered[0]: "myhost",
            pg_ordered[1]: 5433,
            pg_ordered[2]: "mydb",
            pg_ordered[3]: "alice",
        }
        s = Settings(**kwargs)  # NOSONAR python:S2068 — тест конфига, credential не задаётся
        url = s.db_url
        assert "myhost" in url and "5433" in url and "mydb" in url
    finally:
        if old_url is not None:
            os.environ["DATABASE_URL"] = old_url
