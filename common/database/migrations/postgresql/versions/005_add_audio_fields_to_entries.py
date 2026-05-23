"""Add audio fields to entries table

Revision ID: 005_add_audio_fields_to_entries
Revises: 003_add_chat_tables
Create Date: 2026-01-25

Добавляет поля для аудио транскрипции в таблицу entries:
- audio_source - источник аудио ("upload", "stream")
- audio_duration - длительность в секундах
- transcription_model - модель транскрипции (например, "whisper-turbo")
- transcription_language - язык транскрипции ("ru", "en", etc.)
- audio_file_url - URL сохранённого аудио файла (опционально)
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'rev_007'
down_revision: str | None = 'rev_006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Constants for repeated string literals
ENTRIES_TABLE = 'entries'
AUDIO_SOURCE_COLUMN = 'audio_source'
AUDIO_DURATION_COLUMN = 'audio_duration'
TRANSCRIPTION_MODEL_COLUMN = 'transcription_model'
TRANSCRIPTION_LANGUAGE_COLUMN = 'transcription_language'
AUDIO_FILE_URL_COLUMN = 'audio_file_url'
AUDIO_SOURCE_INDEX = 'idx_entries_audio_source'


def upgrade() -> None:
    # Add audio-related columns to entries table
    op.add_column(ENTRIES_TABLE, sa.Column(AUDIO_SOURCE_COLUMN, sa.VARCHAR(50), nullable=True))
    op.add_column(ENTRIES_TABLE, sa.Column(AUDIO_DURATION_COLUMN, sa.FLOAT(), nullable=True))
    op.add_column(ENTRIES_TABLE, sa.Column(TRANSCRIPTION_MODEL_COLUMN, sa.VARCHAR(50), nullable=True))
    op.add_column(ENTRIES_TABLE, sa.Column(TRANSCRIPTION_LANGUAGE_COLUMN, sa.VARCHAR(10), nullable=True))
    op.add_column(ENTRIES_TABLE, sa.Column(AUDIO_FILE_URL_COLUMN, sa.TEXT(), nullable=True))
    
    # Add index for audio_source for filtering
    op.create_index(AUDIO_SOURCE_INDEX, ENTRIES_TABLE, [AUDIO_SOURCE_COLUMN])


def downgrade() -> None:
    # Remove indexes
    op.drop_index(AUDIO_SOURCE_INDEX, table_name=ENTRIES_TABLE)
    
    # Remove columns
    op.drop_column(ENTRIES_TABLE, AUDIO_FILE_URL_COLUMN)
    op.drop_column(ENTRIES_TABLE, TRANSCRIPTION_LANGUAGE_COLUMN)
    op.drop_column(ENTRIES_TABLE, TRANSCRIPTION_MODEL_COLUMN)
    op.drop_column(ENTRIES_TABLE, AUDIO_DURATION_COLUMN)
    op.drop_column(ENTRIES_TABLE, AUDIO_SOURCE_COLUMN)
