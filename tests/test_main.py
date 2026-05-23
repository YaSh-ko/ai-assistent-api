"""Тесты приложения и основных эндпоинтов."""
from fastapi.testclient import TestClient


def test_health(client: TestClient):
    """Health возвращает 200 и status ok."""
    r = client.get("/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "service" in data


def test_docs_available(client: TestClient):
    """Документация доступна."""
    r = client.get("/docs")
    assert r.status_code == 200


def test_openapi_json(client: TestClient):
    """OpenAPI schema отдаётся."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    j = r.json()
    assert "openapi" in j
    assert "paths" in j


def test_options_cors_preflight(client: TestClient):
    """OPTIONS на существующий путь возвращает 200 и CORS-заголовок для разрешённого Origin."""
    # В тестах CORS_ORIGINS обычно включает localhost
    r = client.options(
        "/v1/health", 
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert r.status_code == 200
    assert r.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
