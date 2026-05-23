"""Unit-тесты entry_service (create_entry_and_sync, sync_entry_to_neo4j)."""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.entry_service import create_entry_and_sync, sync_entry_to_neo4j


@pytest.mark.asyncio
async def test_sync_entry_to_neo4j_calls_neo4j():
    """sync_entry_to_neo4j вызывает execute_query_async с параметрами записи."""
    entry = MagicMock()
    entry.id = "entry-uuid"
    entry.user_id = "user-1"
    entry.description = "Hello world"
    entry.event_date = date(2025, 1, 1)
    with patch("src.services.entry_service.neo4j_client") as neo:
        neo.execute_query_async = AsyncMock(return_value=[])
        await sync_entry_to_neo4j(entry, language="ru", duration=1.5)
    neo.execute_query_async.assert_called_once()
    call_kw = neo.execute_query_async.call_args[0][1]
    assert call_kw["entry_id"] == "entry-uuid"
    assert call_kw["user_id"] == "user-1"
    assert call_kw["language"] == "ru"
    assert call_kw["duration"] == pytest.approx(1.5)


@pytest.mark.asyncio
async def test_create_entry_and_sync_returns_created_entry():
    """create_entry_and_sync создаёт запись и синхронизирует с Neo4j."""
    mock_created = MagicMock()
    mock_created.id = "new-id"
    mock_created.user_id = "u1"
    mock_created.description = "desc"
    mock_created.event_date = date(2025, 1, 1)
    db = AsyncMock()
    with patch("src.services.entry_service.EntryRepository") as Repo:
        repo = MagicMock()
        repo.create = AsyncMock(return_value=mock_created)
        Repo.return_value = repo
        with patch("src.services.entry_service.sync_entry_to_neo4j", new_callable=AsyncMock) as sync:
            result = await create_entry_and_sync(
                db=db,
                user_id="u1",
                title="T",
                description="D",
                event_date=date(2025, 1, 1),
            )
    assert result is mock_created
    sync.assert_called_once()
