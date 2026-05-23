"""Тесты эндпоинтов аудио-транскрипции."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.v1.deps import get_current_user_id
from src.api.v1.schemas.audio import TranscriptionResponse, TranscriptionStreamResponse, TranscriptionRequest


@pytest.fixture
def override_user(app):
    """Подмена зависимости get_current_user_id — возвращаем тестовый user_id."""
    def _():
        return "user-test-123"
    app.dependency_overrides[get_current_user_id] = _
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


def test_transcribe_audio_invalid_file_type(client: TestClient, app, override_user):
    """Не аудио/видео файл — 400."""
    r = client.post(
        "/v1/audio/transcribe",
        files={"file": ("x.txt", b"plain text", "text/plain")},
    )
    assert r.status_code == 400
    assert "Invalid file type" in r.json().get("error", "")


def test_transcribe_audio_accepts_audio(client: TestClient, app, override_user):
    """Аудио content-type проходит валидацию; сервис вызывается (мок возвращает entry)."""
    mock_entry = MagicMock()
    mock_entry.id = uuid4()
    mock_entry.description = "Transcribed text"
    mock_entry.transcription_language = "en"
    mock_entry.audio_duration = 1.5
    mock_entry.created_at = datetime(2026, 1, 24, 12, 0, 0)

    with patch("src.api.v1.routes.audio.AudioTranscriptionService") as MockSvc:
        MockSvc.return_value.transcribe_file = AsyncMock(return_value=mock_entry)
        r = client.post(
            "/v1/audio/transcribe",
            files={"file": ("audio.wav", b"\x00" * 100, "audio/wav")},
        )
    assert r.status_code == 201
    data = r.json()
    assert data["text"] == "Transcribed text"
    assert data["language"] == "en"
    assert data["duration"] == pytest.approx(1.5)
    assert "entry_id" in data
    assert "created_at" in data


def test_transcribe_audio_requires_auth(client: TestClient):
    """Без токена — 401 (без override_user)."""
    r = client.post(
        "/v1/audio/transcribe",
        files={"file": ("a.wav", b"\x00" * 10, "audio/wav")},
    )
    assert r.status_code == 401


def test_schemas_audio():
    """Схемы audio сериализуются без ошибок."""
    TranscriptionResponse(
        entry_id=uuid4(),
        text="t",
        language="en",
        duration=0.0,
        created_at="2026-01-24T12:00:00",
    )
    TranscriptionStreamResponse(text="t", is_final=False, entry_id=None)
    TranscriptionStreamResponse(text="done", is_final=True, entry_id=uuid4())
    TranscriptionRequest(title="t", event_date=None, conversation_id=None)
