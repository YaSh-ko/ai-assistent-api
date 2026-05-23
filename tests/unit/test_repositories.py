"""Unit-тесты репозиториев (с моком сессии)."""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from src.data.repositories.base import BaseRepository
from src.data.repositories.conversation import ConversationRepository
from src.data.repositories.entry import EntryRepository
from src.data.repositories.message import MessageRepository
from common.database.models import Conversation


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_conversation_repo_get_by_user_id_returns_list(mock_db):
    """ConversationRepository.get_by_user_id возвращает список."""
    repo = ConversationRepository(mock_db)
    result = await repo.get_by_user_id("user-1", skip=0, limit=10)
    assert result == []
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_conversation_repo_get_recent_calls_get_by_user_id(mock_db):
    """ConversationRepository.get_recent делегирует в get_by_user_id."""
    repo = ConversationRepository(mock_db)
    await repo.get_recent("user-1", limit=5)
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_conversation_repo_get_by_thread_id_returns_none(mock_db):
    """ConversationRepository.get_by_thread_id при отсутствии возвращает None."""
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    repo = ConversationRepository(mock_db)
    result = await repo.get_by_thread_id("thread-1")
    assert result is None


@pytest.mark.asyncio
async def test_entry_repo_get_by_user_id_returns_list(mock_db):
    """EntryRepository.get_by_user_id возвращает список."""
    mock_db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    repo = EntryRepository(mock_db)
    result = await repo.get_by_user_id("user-1", skip=0, limit=10)
    assert result == []


@pytest.mark.asyncio
async def test_message_repo_get_by_conversation_id_returns_list(mock_db):
    """MessageRepository.get_by_conversation_id возвращает список."""
    mock_db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    repo = MessageRepository(mock_db)
    result = await repo.get_by_conversation_id(uuid4(), skip=0, limit=10)
    assert result == []


@pytest.mark.asyncio
async def test_entry_repo_get_recent_calls_get_by_user_id(mock_db):
    """EntryRepository.get_recent делегирует в get_by_user_id."""
    mock_db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    repo = EntryRepository(mock_db)
    result = await repo.get_recent("user-1", limit=5)
    assert result == []


# --- BaseRepository ---

@pytest.mark.asyncio
async def test_base_repo_get_by_id_returns_entity(mock_db):
    """BaseRepository.get_by_id возвращает сущность при наличии."""
    obj = MagicMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=obj))
    repo = BaseRepository(Conversation, mock_db)
    result = await repo.get_by_id(uuid4())
    assert result is obj


@pytest.mark.asyncio
async def test_base_repo_get_by_id_returns_none(mock_db):
    """BaseRepository.get_by_id возвращает None при отсутствии."""
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    repo = BaseRepository(Conversation, mock_db)
    result = await repo.get_by_id(uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_base_repo_get_all_returns_list(mock_db):
    """BaseRepository.get_all возвращает список."""
    mock_db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    repo = BaseRepository(Conversation, mock_db)
    result = await repo.get_all(skip=0, limit=10)
    assert result == []


@pytest.mark.asyncio
async def test_base_repo_create_adds_and_returns_entity(mock_db):
    """BaseRepository.create добавляет сущность и возвращает её."""
    entity = MagicMock()
    mock_db.refresh = AsyncMock(side_effect=lambda e: setattr(entity, "id", uuid4()) or None)
    repo = BaseRepository(Conversation, mock_db)
    result = await repo.create(entity)
    assert result is entity
    mock_db.add.assert_called_once_with(entity)
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_base_repo_update_returns_updated(mock_db):
    """BaseRepository.update вызывает execute, commit и get_by_id."""
    updated = MagicMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    repo = BaseRepository(Conversation, mock_db)
    with patch.object(repo, "get_by_id", new_callable=AsyncMock, return_value=updated):
        result = await repo.update(uuid4(), title="New")
    assert result is updated
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_base_repo_delete_returns_true_when_deleted(mock_db):
    """BaseRepository.delete возвращает True при rowcount > 0."""
    mock_db.execute.return_value = MagicMock(rowcount=1)
    repo = BaseRepository(Conversation, mock_db)
    result = await repo.delete(uuid4())
    assert result is True


@pytest.mark.asyncio
async def test_base_repo_delete_returns_false_when_not_found(mock_db):
    """BaseRepository.delete возвращает False при rowcount == 0."""
    mock_db.execute.return_value = MagicMock(rowcount=0)
    repo = BaseRepository(Conversation, mock_db)
    result = await repo.delete(uuid4())
    assert result is False
