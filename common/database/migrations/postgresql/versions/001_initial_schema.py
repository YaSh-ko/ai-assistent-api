"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-01-17 00:57:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'rev_001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Constants for repeated string literals
USER_ID_COLUMN = 'user_id'
THREAD_ID_COLUMN = 'thread_id'
CREATED_AT_COLUMN = 'created_at'
NOW_DEFAULT = 'now()'
GEN_RANDOM_UUID_DEFAULT = 'gen_random_uuid()'
CASCADE_DELETE = 'CASCADE'
USER_TABLE = 'user'
USER_ID_FK = 'user.id'


def upgrade() -> None:
    # --- user table ---
    op.create_table(
        USER_TABLE,
        sa.Column('id', sa.TEXT(), nullable=False),
        sa.Column('name', sa.TEXT(), nullable=False),
        sa.Column('email', sa.TEXT(), nullable=False),
        sa.Column('emailVerified', sa.Boolean(), nullable=False),
        sa.Column('image', sa.TEXT(), nullable=True),
        sa.Column('createdAt', sa.TIMESTAMP(timezone=True), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.Column('updatedAt', sa.TIMESTAMP(timezone=True), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

    # --- conversations table ---
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column(THREAD_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('llm_provider', sa.VARCHAR(length=50), server_default='gigachat', nullable=False),
        sa.Column('model', sa.VARCHAR(length=100), nullable=True),
        sa.Column('provider_session_id', sa.TEXT(), nullable=True),
        sa.Column('title', sa.TEXT(), nullable=True),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.Column('last_active_at', sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_session_id'),
        sa.UniqueConstraint(THREAD_ID_COLUMN)
    )
    op.create_index('idx_conversations_provider_session_id', 'conversations', ['provider_session_id'], unique=False)
    op.create_index('idx_conversations_thread_id', 'conversations', [THREAD_ID_COLUMN], unique=False)
    op.create_index('idx_conversations_user_id', 'conversations', [USER_ID_COLUMN], unique=False)

    # --- entries table ---
    op.create_table(
        'entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('title', sa.VARCHAR(length=500), nullable=True),
        sa.Column('description', sa.TEXT(), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_entries_event_date', 'entries', ['event_date'], unique=False)
    op.create_index('idx_entries_user_id', 'entries', [USER_ID_COLUMN], unique=False)

    # --- entry_threads table ---
    op.create_table(
        'entry_threads',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('entry_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(THREAD_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint(['entry_id'], ['entries.id'], ondelete=CASCADE_DELETE),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entry_id', THREAD_ID_COLUMN)
    )
    op.create_index('idx_entry_threads_user_entry_thread', 'entry_threads', [USER_ID_COLUMN, 'entry_id', THREAD_ID_COLUMN], unique=False)

    # --- goal_threads table ---
    op.create_table(
        'goal_threads',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(THREAD_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('goal_id', THREAD_ID_COLUMN)
    )
    op.create_index('idx_goal_threads_user_goal_thread', 'goal_threads', [USER_ID_COLUMN, 'goal_id', THREAD_ID_COLUMN], unique=False)

    # --- experiment_threads table ---
    op.create_table(
        'experiment_threads',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(THREAD_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('experiment_id', THREAD_ID_COLUMN)
    )
    op.create_index('idx_experiment_threads_user_experiment_thread', 'experiment_threads', [USER_ID_COLUMN, 'experiment_id', THREAD_ID_COLUMN], unique=False)

    # --- analysis_threads table ---
    op.create_table(
        'analysis_threads',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(THREAD_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_id', THREAD_ID_COLUMN)
    )
    op.create_index('idx_analysis_threads_user_analysis_thread', 'analysis_threads', [USER_ID_COLUMN, 'analysis_id', THREAD_ID_COLUMN], unique=False)


def downgrade() -> None:
    op.drop_table('analysis_threads')
    op.drop_table('experiment_threads')
    op.drop_table('goal_threads')
    op.drop_table('entry_threads')
    op.drop_table('entries')
    op.drop_table('conversations')
    op.drop_table(USER_TABLE)
