"""Тесты эндпоинтов entries (список и recent с моком репозитория)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from fastapi.testclient import TestClient

from src.api.v1.deps import get_current_user_id


async def _mock_user_id():
    await asyncio.sleep(0)
    return "user-1"


@pytest.fixture
def app_entries(app):
    app.dependency_overrides[get_current_user_id] = _mock_user_id
    yield app
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def client_entries(app_entries):
    return TestClient(app_entries)


def test_get_entries_success(client_entries):
    """GET /v1/entries — 200 и список записей."""
    with patch("src.api.v1.routes.entries.EntryRepository") as Repo:
        repo = MagicMock()
        repo.get_by_user_id = AsyncMock(return_value=[])
        Repo.return_value = repo
        r = client_entries.get("/v1/entries")
    assert r.status_code == 200
    assert "entries" in r.json()


def test_get_recent_entries_success(client_entries):
    """GET /v1/entries/recent — 200."""
    with patch("src.api.v1.routes.entries.EntryRepository") as Repo:
        repo = MagicMock()
        repo.get_recent = AsyncMock(return_value=[])
        Repo.return_value = repo
        r = client_entries.get("/v1/entries/recent?limit=5")
    assert r.status_code == 200


def test_create_entry_success(client_entries):
    """POST /v1/entries — 201 при успешном создании."""
    from datetime import date, datetime, timezone
    from uuid import uuid4
    mock_entry = MagicMock()
    mock_entry.id = uuid4()
    mock_entry.user_id = "user-1"
    mock_entry.title = "Title"
    mock_entry.description = "Desc"
    mock_entry.event_date = date(2025, 1, 1)
    mock_entry.created_at = datetime.now(timezone.utc)
    mock_entry.updated_at = datetime.now(timezone.utc)
    create_mock = AsyncMock(return_value=mock_entry)
    with patch("src.api.v1.routes.entries.create_entry_and_sync", create_mock):
        r = client_entries.post(
            "/v1/entries",
            json={"title": "Title", "description": "Desc", "event_date": "2025-01-01"},
        )
    assert r.status_code == 201


def test_get_entry_related_situations_not_found_404(client_entries):
    """GET /v1/entries/{id}/related-situations — 404 если запись не найдена."""
    with patch("src.api.v1.routes.entries.EntryRepository") as ERepo:
        ERepo.return_value.get_by_id = AsyncMock(return_value=None)
        r = client_entries.get(f"/v1/entries/{uuid4()}/related-situations")
    assert r.status_code == 404


def test_get_entry_related_situations_success(client_entries):
    """GET /v1/entries/{id}/related-situations — 200."""
    from datetime import datetime, timezone, date
    entry_id = uuid4()
    mock_entry = MagicMock()
    mock_entry.id = entry_id
    mock_entry.user_id = "user-1"
    with patch("src.api.v1.routes.entries.EntryRepository") as ERepo:
        with patch("src.api.v1.routes.entries.RelatedSituationRepository") as RRepo:
            ERepo.return_value.get_by_id = AsyncMock(return_value=mock_entry)
            RRepo.return_value.get_by_source = AsyncMock(return_value=[])
            r = client_entries.get(f"/v1/entries/{entry_id}/related-situations")
    assert r.status_code == 200
    assert r.json() == []


def test_get_entry_negative_impacts_success(client_entries):
    """GET /v1/entries/{id}/negative-impacts — 200."""
    from uuid import uuid4
    mock_entry = MagicMock()
    mock_entry.id = uuid4()
    mock_entry.user_id = "user-1"
    entry_id = mock_entry.id
    with patch("src.api.v1.routes.entries.EntryRepository") as ERepo:
        with patch("src.api.v1.routes.entries.NegativeImpactRepository") as NRepo:
            ERepo.return_value.get_by_id = AsyncMock(return_value=mock_entry)
            NRepo.return_value.get_by_source = AsyncMock(return_value=[])
            r = client_entries.get(f"/v1/entries/{entry_id}/negative-impacts")
    assert r.status_code == 200
    assert r.json() == []


def test_get_entry_transformations_success(client_entries):
    """GET /v1/entries/{id}/transformations — 200."""
    from uuid import uuid4
    mock_entry = MagicMock()
    mock_entry.id = uuid4()
    mock_entry.user_id = "user-1"
    entry_id = mock_entry.id
    with patch("src.api.v1.routes.entries.EntryRepository") as ERepo:
        with patch("src.api.v1.routes.entries.TransformationRepository") as TRepo:
            ERepo.return_value.get_by_id = AsyncMock(return_value=mock_entry)
            TRepo.return_value.get_by_source = AsyncMock(return_value=[])
            r = client_entries.get(f"/v1/entries/{entry_id}/transformations")
    assert r.status_code == 200
    assert r.json() == []


def test_get_entry_intensity_metrics_not_found_404(client_entries):
    """GET /v1/entries/{id}/intensity-metrics — 404 если запись не найдена."""
    from uuid import uuid4
    with patch("src.api.v1.routes.entries.EntryRepository") as ERepo:
        ERepo.return_value.get_by_id = AsyncMock(return_value=None)
        r = client_entries.get(f"/v1/entries/{uuid4()}/intensity-metrics")
    assert r.status_code == 404


def test_get_entry_intensity_metrics_success(client_entries):
    """GET /v1/entries/{id}/intensity-metrics — 200."""
    from uuid import uuid4
    from datetime import datetime, timezone, date
    entry_id = uuid4()
    mock_entry = MagicMock()
    mock_entry.id = entry_id
    mock_entry.user_id = "user-1"
    with patch("src.api.v1.routes.entries.EntryRepository") as ERepo:
        with patch("src.api.v1.routes.entries.IntensityMetricRepository") as MRepo:
            ERepo.return_value.get_by_id = AsyncMock(return_value=mock_entry)
            MRepo.return_value.get_by_entity = AsyncMock(return_value=[])
            r = client_entries.get(f"/v1/entries/{entry_id}/intensity-metrics")
    assert r.status_code == 200
    assert r.json() == []


def test_get_entry_analysis_not_found_404(client_entries):
    """GET /v1/entries/{id}/analysis — 404 если запись не найдена или чужая."""
    from uuid import uuid4
    with patch("src.api.v1.routes.entries.EntryRepository") as ERepo:
        ERepo.return_value.get_by_id = AsyncMock(return_value=None)
        r = client_entries.get(f"/v1/entries/{uuid4()}/analysis")
    assert r.status_code == 404


def test_get_entry_analysis_success(client_entries):
    """GET /v1/entries/{id}/analysis — 200 и анализ."""
    from uuid import uuid4
    from datetime import date, datetime, timezone
    entry_id = uuid4()
    mock_entry = MagicMock()
    mock_entry.id = entry_id
    mock_entry.user_id = "user-1"
    mock_entry.title = "T"
    mock_entry.description = "D"
    mock_entry.event_date = date(2025, 1, 1)
    mock_entry.created_at = datetime.now(timezone.utc)
    mock_entry.updated_at = datetime.now(timezone.utc)
    with patch("src.api.v1.routes.entries.EntryRepository") as ERepo:
        with patch("src.api.v1.routes.entries.IntensityMetricRepository") as MRepo:
            with patch("src.api.v1.routes.entries.RelatedSituationRepository") as RRepo:
                with patch("src.api.v1.routes.entries.NegativeImpactRepository") as NRepo:
                    with patch("src.api.v1.routes.entries.TransformationRepository") as TRepo:
                        with patch("src.api.v1.routes.entries.neo4j_client") as neo:
                            ERepo.return_value.get_by_id = AsyncMock(return_value=mock_entry)
                            MRepo.return_value.get_by_entity = AsyncMock(return_value=[])
                            RRepo.return_value.get_by_source = AsyncMock(return_value=[])
                            NRepo.return_value.get_by_source = AsyncMock(return_value=[])
                            TRepo.return_value.get_by_source = AsyncMock(return_value=[])
                            neo.get_related_nodes = AsyncMock(return_value=[])
                            r = client_entries.get(f"/v1/entries/{entry_id}/analysis")
    assert r.status_code == 200
    assert "entry" in r.json()
