"""
Entry service - create entries and sync to Neo4j.
ChromaDB sync can be added here when needed.
"""
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from common.database.models import Entry
from src.data.repositories.entry import EntryRepository
from src.infrastructure.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


async def sync_entry_to_neo4j(
    entry: Entry,
    language: str = "",
    duration: float = 0.0,
) -> None:
    """Sync Entry to Neo4j graph. Does not raise on failure."""
    try:
        query = """
        MERGE (e:Entry {id: $entry_id})
        SET e.user_id = $user_id,
            e.title = $title,
            e.content = $content,
            e.timestamp = datetime($timestamp),
            e.word_count = $word_count,
            e.transcription_language = $language,
            e.audio_duration = $duration,
            e.life_area = $life_area,
            e.updated_at = datetime()
        RETURN e
        """
        word_count = len((entry.description or "").split())
        timestamp = datetime.combine(entry.event_date, datetime.min.time())
        await neo4j_client.execute_query_async(
            query,
            {
                "entry_id": str(entry.id),
                "user_id": entry.user_id,
                "title": (entry.title or "")[:500],
                "content": entry.description or "",
                "life_area": entry.life_area,
                "timestamp": timestamp.isoformat(),
                "word_count": word_count,
                "language": language,
                "duration": duration,
            },
        )
        logger.info("Entry %s synced to Neo4j", entry.id)
    except Exception as e:
        logger.error("Error syncing entry to Neo4j: %s", e)


async def create_entry_and_sync(
    db: AsyncSession,
    user_id: str,
    title: str,
    description: str,
    event_date,
    life_area: str | None = None,
) -> Entry:
    """Create entry in DB, sync to Neo4j, and create semantic links."""
    from src.services.semantic_linker import semantic_link_entity

    entry = Entry(
        user_id=user_id,
        title=title,
        description=description,
        event_date=event_date,
        life_area=life_area,
    )
    repo = EntryRepository(db)
    created = await repo.create(entry)
    await sync_entry_to_neo4j(created, language="", duration=0.0)
    logger.info(
        "[EntryService] Trigger semantic link: entry=%s area=%s title=%r desc_len=%d",
        created.id,
        life_area or "-",
        (title or "")[:60],
        len(description or ""),
    )
    links = await semantic_link_entity(
        entity_id=str(created.id),
        entity_type="observation",
        title=title,
        description=description,
        user_id=user_id,
        db=db,
        life_area=life_area,
    )
    logger.info(
        "[EntryService] Semantic link done: entry=%s links_created=%d",
        created.id,
        len(links),
    )
    return created


async def delete_entry_from_neo4j(entry_id: str) -> None:
    """Remove Entry node and its relationships from Neo4j."""
    try:
        await neo4j_client.execute_query_async(
            "MATCH (e:Entry {id: $id}) DETACH DELETE e",
            {"id": entry_id},
        )
        logger.info("Entry %s deleted from Neo4j", entry_id)
    except Exception as e:
        logger.error("Error deleting entry from Neo4j: %s", e)


async def delete_entry_and_sync(db: AsyncSession, entry_id: str, user_id: str) -> bool:
    from uuid import UUID

    try:
        eid = UUID(entry_id)
    except ValueError:
        return False

    repo = EntryRepository(db)
    entry = await repo.get_by_id(eid)
    if not entry or entry.user_id != user_id:
        return False

    deleted = await repo.delete(eid)
    if deleted:
        await delete_entry_from_neo4j(entry_id)
    return deleted
