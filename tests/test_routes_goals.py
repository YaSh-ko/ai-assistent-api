"""Тесты эндпоинтов goals (с моками neo4j и get_current_user_id)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.api.v1.deps import get_current_user_id


async def _mock_user_id():
    await asyncio.sleep(0)
    return "user-1"


@pytest.fixture
def app_goals(app):
    app.dependency_overrides[get_current_user_id] = _mock_user_id
    yield app
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def client_goals(app_goals):
    return TestClient(app_goals)


def test_get_goals_list_success(client_goals):
    """GET /v1/goals — 200 и список целей."""
    from datetime import datetime
    now = datetime.now().isoformat()
    with patch("src.api.v1.routes.goals.neo4j_client") as neo:
        neo.execute_query_async = AsyncMock(return_value=[
            {"g": {"id": "g1", "user_id": "user-1", "title": "Goal 1", "description": None,
                   "status": "active", "priority": None, "created_at": now, "target_date": None,
                   "achieved_at": None, "updated_at": now}},
        ])
        r = client_goals.get("/v1/goals")
    assert r.status_code == 200
    assert "goals" in r.json()


def test_get_goal_by_id_success(client_goals):
    """GET /v1/goals/{id} — 200 при своей цели."""
    from datetime import datetime
    now = datetime.now().isoformat()
    with patch("src.api.v1.routes.goals.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={
            "id": "g1", "user_id": "user-1", "title": "My goal", "description": None,
            "status": "active", "priority": None, "created_at": now, "target_date": None,
            "achieved_at": None, "updated_at": now,
        })
        r = client_goals.get("/v1/goals/g1")
    assert r.status_code == 200
    assert r.json()["user_id"] == "user-1"


def test_get_goal_not_found(client_goals):
    """GET /v1/goals/{id} — 404."""
    with patch("src.api.v1.routes.goals.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value=None)
        r = client_goals.get("/v1/goals/bad")
    assert r.status_code == 404


def test_get_goal_forbidden(client_goals):
    """GET /v1/goals/{id} — 403 чужой цель."""
    with patch("src.api.v1.routes.goals.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={
            "id": "g2", "user_id": "other", "title": "Other",
        })
        r = client_goals.get("/v1/goals/g2")
    assert r.status_code == 403


def test_get_goal_related_entries_success(client_goals):
    """GET /v1/goals/{id}/related-entries — 200 и список."""
    from datetime import datetime
    now = datetime.now().isoformat()
    with patch("src.api.v1.routes.goals.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": "g1", "user_id": "user-1"})
        neo.get_related_nodes = AsyncMock(return_value=[
            {"id": "e1", "content": "x", "timestamp": now, "user_id": "user-1"},
        ])
        r = client_goals.get("/v1/goals/g1/related-entries")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_goal_concepts_success(client_goals):
    """GET /v1/goals/{id}/concepts — 200 и список."""
    from datetime import datetime
    now = datetime.now().isoformat()
    with patch("src.api.v1.routes.goals.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": "g1", "user_id": "user-1"})
        neo.get_related_nodes = AsyncMock(return_value=[
            {"id": "c1", "name": "C1", "user_id": "user-1", "created_at": now, "updated_at": now},
        ])
        r = client_goals.get("/v1/goals/g1/concepts")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_goal_related_entries_not_found_404(client_goals):
    """GET /v1/goals/{id}/related-entries — 404 если цель не найдена."""
    with patch("src.api.v1.routes.goals.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value=None)
        r = client_goals.get("/v1/goals/bad-id/related-entries")
    assert r.status_code == 404


def test_get_goal_concepts_not_found_404(client_goals):
    """GET /v1/goals/{id}/concepts — 404 если цель не найдена."""
    with patch("src.api.v1.routes.goals.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value=None)
        r = client_goals.get("/v1/goals/bad-id/concepts")
    assert r.status_code == 404
