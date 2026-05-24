"""Tests for goals and experiments create (mocked service)."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.v1.deps import get_current_user_id


async def _mock_user_id():
    await asyncio.sleep(0)
    return "user-goals-1"


@pytest.fixture
def app_goals(app):
    app.dependency_overrides[get_current_user_id] = _mock_user_id
    yield app
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def client_goals(app_goals):
    return TestClient(app_goals)


def test_create_goal_success(client_goals):
    """POST /v1/goals — 201 при успешном создании."""
    from common.database.models import Goal

    goal_id = uuid4()
    now = datetime.now(timezone.utc)
    mock_goal = Goal(
        id=goal_id,
        user_id="user-goals-1",
        title="Бегать",
        description="3 раза в неделю",
        status="active",
        priority="medium",
        target_date=None,
        achieved_at=None,
        created_at=now,
        updated_at=now,
    )
    with patch(
        "src.api.v1.routes.goals.create_goal_and_sync",
        AsyncMock(return_value=mock_goal),
    ):
        r = client_goals.post(
            "/v1/goals",
            json={"title": "Бегать", "description": "3 раза в неделю"},
        )
    assert r.status_code == 201
    assert r.json()["id"] == str(goal_id)


def test_create_experiment_success(client_goals):
    """POST /v1/experiments — 201 при успешном создании."""
    from common.database.models import Experiment

    exp_id = uuid4()
    now = datetime.now(timezone.utc)
    mock_exp = Experiment(
        id=exp_id,
        user_id="user-goals-1",
        title="Медитация",
        description="10 минут утром",
        status="active",
        success=0,
        outcome="",
        started_at=now,
        ended_at=None,
        created_at=now,
        updated_at=now,
    )
    with patch(
        "src.api.v1.routes.experiments.create_experiment_and_sync",
        AsyncMock(return_value=mock_exp),
    ):
        r = client_goals.post(
            "/v1/experiments",
            json={"title": "Медитация", "description": "10 минут утром"},
        )
    assert r.status_code == 201
    assert r.json()["id"] == str(exp_id)
