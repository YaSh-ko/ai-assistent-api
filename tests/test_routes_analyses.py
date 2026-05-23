"""Тесты эндпоинтов analyses (с моками neo4j и get_current_user_id)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.api.v1.deps import get_current_user_id


async def _mock_user_id():
    await asyncio.sleep(0)
    return "user-1"


@pytest.fixture
def app_with_auth(app):
    """Приложение с подменённым get_current_user_id."""
    app.dependency_overrides[get_current_user_id] = _mock_user_id
    yield app
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def client_analyses(app_with_auth):
    return TestClient(app_with_auth)


def test_get_analysis_success(client_analyses):
    """GET /v1/analyses/{id} — 200 при найденном анализе."""
    from datetime import datetime
    with patch("src.api.v1.routes.analyses.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={
            "id": "a1", "user_id": "user-1", "title": "Test",
            "content": "x", "summary": None, "analyzed_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(),
        })
        r = client_analyses.get("/v1/analyses/a1")
    assert r.status_code == 200
    assert r.json()["user_id"] == "user-1"


def test_get_analysis_not_found(client_analyses):
    """GET /v1/analyses/{id} — 404 если анализа нет."""
    with patch("src.api.v1.routes.analyses.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value=None)
        r = client_analyses.get("/v1/analyses/bad")
    assert r.status_code == 404


def test_get_analysis_forbidden(client_analyses):
    """GET /v1/analyses/{id} — 403 чужой анализ."""
    with patch("src.api.v1.routes.analyses.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={
            "id": "a2", "user_id": "other-user", "title": "Other",
        })
        r = client_analyses.get("/v1/analyses/a2")
    assert r.status_code == 403


def test_get_analysis_concepts_success(client_analyses):
    """GET /v1/analyses/{id}/concepts — 200 и список."""
    from datetime import datetime
    now = datetime.now().isoformat()
    with patch("src.api.v1.routes.analyses.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": "a1", "user_id": "user-1"})
        neo.get_related_nodes = AsyncMock(return_value=[
            {"id": "c1", "name": "Concept 1", "user_id": "user-1", "created_at": now, "updated_at": now},
        ])
        r = client_analyses.get("/v1/analyses/a1/concepts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_analysis_goals_success(client_analyses):
    """GET /v1/analyses/{id}/goals — 200 и список."""
    with patch("src.api.v1.routes.analyses.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": "a1", "user_id": "user-1"})
        neo.get_related_nodes = AsyncMock(return_value=[])
        r = client_analyses.get("/v1/analyses/a1/goals")
    assert r.status_code == 200
    assert r.json() == []


def test_get_analysis_experiments_success(client_analyses):
    """GET /v1/analyses/{id}/experiments — 200 и список."""
    with patch("src.api.v1.routes.analyses.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": "a1", "user_id": "user-1"})
        neo.get_related_nodes = AsyncMock(return_value=[])
        r = client_analyses.get("/v1/analyses/a1/experiments")
    assert r.status_code == 200
    assert r.json() == []


def test_get_analysis_concepts_not_found(client_analyses):
    """GET /v1/analyses/{id}/concepts — 404 если анализ не найден или чужой."""
    with patch("src.api.v1.routes.analyses.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value=None)
        r = client_analyses.get("/v1/analyses/bad/concepts")
    assert r.status_code == 404


def test_get_analysis_goals_not_found(client_analyses):
    """GET /v1/analyses/{id}/goals — 404 если анализ не найден."""
    with patch("src.api.v1.routes.analyses.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value=None)
        r = client_analyses.get("/v1/analyses/bad/goals")
    assert r.status_code == 404


def test_get_analysis_experiments_not_found(client_analyses):
    """GET /v1/analyses/{id}/experiments — 404 если анализ не найден."""
    with patch("src.api.v1.routes.analyses.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value=None)
        r = client_analyses.get("/v1/analyses/bad/experiments")
    assert r.status_code == 404


def test_get_analysis_concepts_forbidden(client_analyses):
    """GET /v1/analyses/{id}/concepts — 404 при чужом анализе (скрываем факт)."""
    with patch("src.api.v1.routes.analyses.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": "a1", "user_id": "other-user"})
        r = client_analyses.get("/v1/analyses/a1/concepts")
    assert r.status_code == 404
