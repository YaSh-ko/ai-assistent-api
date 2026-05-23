"""Тесты сервиса аудио-транскрипции."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.audio_transcription_service import AudioTranscriptionService


@pytest.fixture
def mock_db():
    """Мок сессии БД."""
    db = MagicMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    return db


class _FakeEntry:
    """Подмена Entry в тесте: принимает любые kwargs (совместимость с разными версиями common)."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.asyncio
async def test_transcribe_file_success(mock_db):
    """transcribe_file возвращает entry при успешной транскрипции."""
    mock_whisper = MagicMock()
    mock_whisper.model_name = "turbo"
    mock_whisper.transcribe_file = AsyncMock(
        return_value={"text": "Hello world", "language": "en", "duration": 1.5}
    )
    created = MagicMock()
    created.id = uuid4()
    created.description = "Hello world"
    created.transcription_language = "en"
    created.audio_duration = 1.5
    created.event_date = date.today()
    created.user_id = "u1"
    mock_repo = MagicMock()
    mock_repo.create = AsyncMock(return_value=created)

    with patch("src.services.audio_transcription_service.get_whisper_client", return_value=mock_whisper), \
         patch("src.services.audio_transcription_service.Entry", _FakeEntry), \
         patch("src.services.audio_transcription_service.EntryRepository", return_value=mock_repo), \
         patch("src.services.audio_transcription_service.neo4j_client") as neo_mock:
        neo_mock.execute_query_async = AsyncMock()
        svc = AudioTranscriptionService(mock_db)
        svc.whisper_client = mock_whisper
        svc.entry_repo = mock_repo
        fake_file = MagicMock()
        entry = await svc.transcribe_file(
            audio_file=fake_file, user_id="u1", title="Test", event_date=date.today()
        )
    assert entry.description == "Hello world"
    assert entry.transcription_language == "en"
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_transcribe_file_empty_text_raises(mock_db):
    """transcribe_file при пустом тексте от Whisper выбрасывает ValueError."""
    mock_whisper = MagicMock()
    mock_whisper.model_name = "turbo"
    mock_whisper.transcribe_file = AsyncMock(
        return_value={"text": "", "language": "en", "duration": 0.0}
    )
    with patch("src.services.audio_transcription_service.get_whisper_client", return_value=mock_whisper), \
         patch("src.services.audio_transcription_service.EntryRepository"):
        svc = AudioTranscriptionService(mock_db)
        svc.whisper_client = mock_whisper
        svc.entry_repo = MagicMock()
        with pytest.raises(ValueError, match="empty text"):
            await svc.transcribe_file(
                audio_file=MagicMock(), user_id="u1"
            )
    mock_db.rollback.assert_awaited_once()
