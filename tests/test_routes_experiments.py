"""Тесты эндпоинтов experiments (с моками neo4j и get_current_user_id)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.api.v1.deps import get_current_user_id


async def _mock_user_id():
    await asyncio.sleep(0)
    return "user-1"


@pytest.fixture
def app_experiments(app):
    app.dependency_overrides[get_current_user_id] = _mock_user_id
    yield app
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def client_experiments(app_experiments):
    return TestClient(app_experiments)


def test_get_experiment_success(client_experiments):
    """GET /v1/experiments/{id} — 200 при своём эксперименте."""
    from datetime import datetime
    now = datetime.now().isoformat()
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={
            "id": "e1", "user_id": "user-1", "title": "Exp 1", "description": None,
            "status": "active", "started_at": None, "ended_at": None, "outcome": None,
            "success": None, "created_at": now, "updated_at": now,
        })
        neo.get_entries_documenting_experiment = AsyncMock(return_value=[])
        neo.get_related_nodes = AsyncMock(return_value=[])
        with patch("src.api.v1.routes.experiments.IntensityMetricRepository") as Repo:
            repo = MagicMock()
            repo.get_by_entity = AsyncMock(return_value=[])
            Repo.return_value = repo
            r = client_experiments.get("/v1/experiments/e1")
    assert r.status_code == 200
    body = r.json()
    assert body["experiment"]["user_id"] == "user-1"
    assert body["intensity_metrics"]["data_points"] == []
    assert body["related_entries"] == []
    assert body["tested_concepts"] == []


def test_get_experiment_not_found(client_experiments):
    """GET /v1/experiments/{id} — 404."""
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value=None)
        r = client_experiments.get("/v1/experiments/bad")
    assert r.status_code == 404


def test_get_experiment_forbidden(client_experiments):
    """GET /v1/experiments/{id} — 403 чужой эксперимент."""
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={
            "id": "e2", "user_id": "other", "title": "Other",
        })
        r = client_experiments.get("/v1/experiments/e2")
    assert r.status_code == 403


def test_get_experiment_intensity_metrics_success(client_experiments):
    """GET /v1/experiments/{id}/intensity-metrics — 200 и список метрик."""
    from datetime import datetime
    now = datetime.now().isoformat()
    exp_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={
            "id": exp_id, "user_id": "user-1", "title": "E", "status": "active",
            "created_at": now, "updated_at": now,
        })
        with patch("src.api.v1.routes.experiments.IntensityMetricRepository") as Repo:
            repo = MagicMock()
            repo.get_by_entity = AsyncMock(return_value=[])
            repo.get_by_entity_period = AsyncMock(return_value=[])
            Repo.return_value = repo
            r = client_experiments.get(f"/v1/experiments/{exp_id}/intensity-metrics")
    assert r.status_code == 200
    assert r.json() == []


def test_get_experiment_intensity_metrics_prefixed_neo4j_id(client_experiments):
    """GET /v1/experiments/{id}/intensity-metrics — 200 при id вида prefix_UUID (Neo4j)."""
    from datetime import datetime
    from uuid import UUID

    now = datetime.now().isoformat()
    inner = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    exp_id = f"exp_ann_running_{inner}"
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={
            "id": exp_id, "user_id": "user-1", "title": "E", "status": "active",
            "created_at": now, "updated_at": now,
        })
        with patch("src.api.v1.routes.experiments.IntensityMetricRepository") as Repo:
            repo = MagicMock()
            repo.get_by_entity = AsyncMock(return_value=[])
            repo.get_by_entity_period = AsyncMock(return_value=[])
            Repo.return_value = repo
            r = client_experiments.get(
                f"/v1/experiments/{exp_id}/intensity-metrics?period=week"
            )
    assert r.status_code == 200
    repo = Repo.return_value
    repo.get_by_entity_period.assert_called_once()
    args, _ = repo.get_by_entity_period.call_args
    assert args[0] == "experiment"
    assert args[1] == UUID(inner)
    assert args[2] == "week"


def test_create_experiment_intensity_metric_success(client_experiments):
    """POST /v1/experiments/{id}/intensity-metrics — 201."""
    from uuid import uuid4
    from datetime import date, datetime, timezone
    exp_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    now = datetime.now(timezone.utc)
    mock_metric = MagicMock()
    mock_metric.id = uuid4()
    mock_metric.user_id = "user-1"
    mock_metric.entity_type = "experiment"
    mock_metric.entity_id = uuid4()
    mock_metric.intensity_value = 7
    mock_metric.metric_date = date(2025, 1, 15)
    mock_metric.note = None
    mock_metric.created_at = now
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": exp_id, "user_id": "user-1", "title": "E", "status": "active", "created_at": now.isoformat(), "updated_at": now.isoformat()})
        with patch("src.api.v1.routes.experiments.IntensityMetric", return_value=mock_metric):
            r = client_experiments.post(
                f"/v1/experiments/{exp_id}/intensity-metrics",
                json={"intensity_value": 7, "metric_date": "2025-01-15"},
            )
    assert r.status_code == 201


def test_get_experiment_entries_success(client_experiments):
    """GET /v1/experiments/{id}/entries — 200 и список."""
    from datetime import datetime
    now = datetime.now().isoformat()
    exp_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": exp_id, "user_id": "user-1"})
        neo.get_entries_documenting_experiment = AsyncMock(
            return_value=[{"id": "ent1", "content": "x", "timestamp": now, "user_id": "user-1"}]
        )
        r = client_experiments.get(f"/v1/experiments/{exp_id}/entries")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_experiment_intensity_metric_invalid_uuid_400(client_experiments):
    """POST /v1/experiments/{id}/intensity-metrics — 400 при невалидном UUID."""
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": "not-a-uuid", "user_id": "user-1"})
        r = client_experiments.post(
            "/v1/experiments/not-a-uuid/intensity-metrics",
            json={"intensity_value": 5, "metric_date": "2025-01-01"},
        )
    assert r.status_code == 400


def test_get_experiment_entries_not_found_404(client_experiments):
    """GET /v1/experiments/{id}/entries — 404 если эксперимент не найден."""
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value=None)
        r = client_experiments.get("/v1/experiments/bad-id/entries")
    assert r.status_code == 404


def test_get_experiment_summary_invalid_uuid_400(client_experiments):
    """GET /v1/experiments/{id}/summary — 400 при невалидном UUID."""
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": "x", "user_id": "user-1"})
        r = client_experiments.get("/v1/experiments/not-uuid/summary")
    assert r.status_code == 400


def test_get_experiment_summary_success(client_experiments):
    """GET /v1/experiments/{id}/summary — 200."""
    from datetime import datetime
    now = datetime.now().isoformat()
    exp_id = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    with patch("src.api.v1.routes.experiments.neo4j_client") as neo:
        neo.get_node_by_id = AsyncMock(return_value={"id": exp_id, "user_id": "user-1", "title": "E", "status": "active", "created_at": now, "updated_at": now})
        with patch("src.api.v1.routes.experiments.IntensityMetricRepository") as Repo:
            repo = MagicMock()
            repo.get_by_entity = AsyncMock(return_value=[])
            repo.get_average_intensity = AsyncMock(return_value=5.5)
            Repo.return_value = repo
            r = client_experiments.get(f"/v1/experiments/{exp_id}/summary")
    assert r.status_code == 200
    assert "experiment" in r.json()
