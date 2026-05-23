"""
Audio transcription service.
Service layer for audio transcription business logic (Вариант 2).
"""
import logging
from typing import Optional, AsyncGenerator
from datetime import date, datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.whisper_streaming_client import get_whisper_client
from src.data.repositories.entry import EntryRepository
from src.infrastructure.neo4j_client import neo4j_client
from common.database.models import Entry

logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    """Service for audio transcription and Entry creation."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.whisper_client = get_whisper_client()
        self.entry_repo = EntryRepository(db)
    
    async def transcribe_file(
        self,
        audio_file,
        user_id: str,
        title: Optional[str] = None,
        event_date: Optional[date] = None,
    ) -> Entry:
        """
        Transcribe audio file and create Entry.

        Args:
            audio_file: Uploaded audio file
            user_id: User ID
            title: Optional title for entry
            event_date: Optional event date (defaults to today)

        Returns:
            Created Entry
        """
        try:
            # Transcribe audio
            logger.info(f"Starting transcription for user {user_id}")
            transcription_result = await self.whisper_client.transcribe_file(audio_file)
            
            text = transcription_result.get("text", "")
            language = transcription_result.get("language", "unknown")
            duration = transcription_result.get("duration", 0.0)
            
            if not text:
                raise ValueError("Transcription resulted in empty text")
            
            # Create Entry
            entry = Entry(
                user_id=user_id,
                title=title or f"Audio transcription ({language})",
                description=text,
                event_date=event_date or date.today(),
                audio_source="upload",
                audio_duration=duration,
                transcription_model=f"whisper-{self.whisper_client.model_name}",
                transcription_language=language,
            )
            
            created_entry = await self.entry_repo.create(entry)
            await self.db.commit()
            await self.db.refresh(created_entry)
            
            # Sync with Neo4j
            await self._sync_entry_to_neo4j(created_entry, language, duration)
            
            logger.info(f"Entry {created_entry.id} created from audio transcription")
            return created_entry
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error in transcribe_file: {e}")
            raise
    
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        user_id: str,
        title: Optional[str] = None,
        event_date: Optional[date] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Transcribe audio stream and create Entry when complete.

        Args:
            audio_stream: Async generator of audio chunks
            user_id: User ID
            title: Optional title for entry
            event_date: Optional event date

        Yields:
            dict with transcription updates:
            {
                "text": str,
                "is_final": bool,
                "entry_id": Optional[UUID]
            }
        """
        try:
            full_text_parts = []
            language = None
            duration = 0.0
            
            # Process streaming transcription
            async for result in self.whisper_client.transcribe_stream(audio_stream):
                text = result.get("text", "")
                language = result.get("language", language)
                
                if text:
                    full_text_parts.append(text)
                    
                    yield {
                        "text": text,
                        "is_final": False,
                        "entry_id": None
                    }
            
            # Create Entry when stream is complete
            if full_text_parts:
                full_text = " ".join(full_text_parts)
                
                entry = Entry(
                    user_id=user_id,
                    title=title or f"Audio stream transcription ({language or 'unknown'})",
                    description=full_text,
                    event_date=event_date or date.today(),
                    audio_source="stream",
                    audio_duration=duration,
                    transcription_model=f"whisper-{self.whisper_client.model_name}",
                    transcription_language=language,
                )
                
                created_entry = await self.entry_repo.create(entry)
                await self.db.commit()
                await self.db.refresh(created_entry)
                
                # Sync with Neo4j
                await self._sync_entry_to_neo4j(
                    created_entry, language or "unknown", duration
                )
                
                # Yield final result
                yield {
                    "text": full_text,
                    "is_final": True,
                    "entry_id": str(created_entry.id)
                }
                
                logger.info(f"Entry {created_entry.id} created from audio stream")
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error in transcribe_stream: {e}")
            raise
    
    async def _sync_entry_to_neo4j(
        self,
        entry: Entry,
        language: str,
        duration: float
    ):
        """Sync Entry to Neo4j graph database."""
        try:
            query = """
            MERGE (e:Entry {id: $entry_id})
            SET e.user_id = $user_id,
                e.content = $content,
                e.timestamp = datetime($timestamp),
                e.word_count = $word_count,
                e.transcription_language = $language,
                e.audio_duration = $duration,
                e.updated_at = datetime()
            RETURN e
            """
            
            word_count = len(entry.description.split())
            timestamp = datetime.combine(entry.event_date, datetime.min.time())
            
            await neo4j_client.execute_query_async(
                query,
                {
                    "entry_id": str(entry.id),
                    "user_id": entry.user_id,
                    "content": entry.description,
                    "timestamp": timestamp.isoformat(),
                    "word_count": word_count,
                    "language": language,
                    "duration": duration
                }
            )
            
            logger.info(f"Entry {entry.id} synced to Neo4j")
            
        except Exception as e:
            logger.error(f"Error syncing entry to Neo4j: {e}")
            # Don't raise - Neo4j sync failure shouldn't break the flow
