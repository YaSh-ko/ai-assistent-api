"""Тесты эндпоинтов graph (rhizome, search)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.api.v1.deps import get_current_user_id


async def _mock_user_id():
    await asyncio.sleep(0)
    return "user-1"


@pytest.fixture
def app_graph(app):
    app.dependency_overrides[get_current_user_id] = _mock_user_id
    yield app
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def client_graph(app_graph):
    return TestClient(app_graph)


def test_get_rhizome_graph_success(client_graph):
    """GET /v1/graph/rhizome — 200 и граф."""
    with patch("src.api.v1.routes.graph.neo4j_client") as neo:
        neo.get_rhizome_graph = AsyncMock(return_value={"nodes": [], "links": []})
        r = client_graph.get("/v1/graph/rhizome")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data and "links" in data


def test_get_rhizome_graph_with_query_params(client_graph):
    """GET /v1/graph/rhizome с параметрами."""
    with patch("src.api.v1.routes.graph.neo4j_client") as neo:
        neo.get_rhizome_graph = AsyncMock(return_value={"nodes": [], "links": []})
        r = client_graph.get("/v1/graph/rhizome?node_types=Goal&time_period=past")
    assert r.status_code == 200


def test_get_rhizome_graph_exception_500(client_graph):
    """GET /v1/graph/rhizome при исключении из neo4j — 500."""
    with patch("src.api.v1.routes.graph.neo4j_client") as neo:
        neo.get_rhizome_graph = AsyncMock(side_effect=RuntimeError("neo4j down"))
        r = client_graph.get("/v1/graph/rhizome")
    assert r.status_code == 500


def test_search_graph_nodes_exception_500(client_graph):
    """GET /v1/graph/search при исключении — 500."""
    with patch("src.api.v1.routes.graph.neo4j_client") as neo:
        neo.search_nodes = AsyncMock(side_effect=ValueError("search failed"))
        r = client_graph.get("/v1/graph/search?query=x&limit=10")
    assert r.status_code == 500


def test_search_graph_nodes_success(client_graph):
    """GET /v1/graph/search — 200 и список узлов."""
    with patch("src.api.v1.routes.graph.neo4j_client") as neo:
        neo.search_nodes = AsyncMock(return_value=[
            {"id": "n1", "user": "user-1", "description": "d", "type": "Goal"},
        ])
        r = client_graph.get("/v1/graph/search?query=test&limit=10")
    assert r.status_code == 200
    assert "nodes" in r.json()
