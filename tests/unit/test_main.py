# tests/unit/test_main.py
import pytest

def test_health(client):
    """Тест эндпоинта /health."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data

def test_docs(client):
    """Тест документации."""
    response = client.get("/docs")
    assert response.status_code == 200

def test_main_import():
    """Просто проверяем, что модуль импортируется без ошибок."""
    import src.main
    assert src.main is not None

def test_config_import():
    """Проверяем импорт конфигурации."""
    from src.core import config
    assert hasattr(config, 'settings')