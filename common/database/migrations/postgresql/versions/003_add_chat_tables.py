"""Add chat and analytics tables

Revision ID: 003_add_chat_and_analytics_tables
Revises: 002_add_auth_tables
Create Date: 2026-01-20

Добавляет таблицы:
- messages - сообщения диалога для agent-chat-ui
- message_reactions - реакции на сообщения
- intensity_metrics - метрики интенсивности для графиков
- related_situations - связанные ситуации
- negative_impacts - негативные последствия
- transformations - трансформации/уроки
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'rev_005'
down_revision: str | None = 'rev_004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Constants for repeated string literals
USER_ID_COLUMN = 'user_id'
CREATED_AT_COLUMN = 'created_at'
SOURCE_TYPE_COLUMN = 'source_type'
SOURCE_ID_COLUMN = 'source_id'
NOW_DEFAULT = 'now()'
GEN_RANDOM_UUID_DEFAULT = 'gen_random_uuid()'
CASCADE_DELETE = 'CASCADE'
USER_ID_FK = 'user.id'
MESSAGES_TABLE = 'messages'
MESSAGE_REACTIONS_TABLE = 'message_reactions'
INTENSITY_METRICS_TABLE = 'intensity_metrics'
RELATED_SITUATIONS_TABLE = 'related_situations'
NEGATIVE_IMPACTS_TABLE = 'negative_impacts'
TRANSFORMATIONS_TABLE = 'transformations'


def upgrade() -> None:
    # === messages ===
    op.create_table(
        MESSAGES_TABLE,
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('role', sa.VARCHAR(20), nullable=False),
        sa.Column('content', sa.TEXT(), nullable=False),
        sa.Column('metadata', sa.TEXT(), nullable=True),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(timezone=True), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete=CASCADE_DELETE),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_messages_conversation_id', MESSAGES_TABLE, ['conversation_id'])
    op.create_index('idx_messages_user_id', MESSAGES_TABLE, [USER_ID_COLUMN])
    op.create_index('idx_messages_created_at', MESSAGES_TABLE, [CREATED_AT_COLUMN])

    # === message_reactions ===
    op.create_table(
        MESSAGE_REACTIONS_TABLE,
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('reaction_type', sa.VARCHAR(50), nullable=False),
        sa.Column('emoji', sa.VARCHAR(10), nullable=True),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(timezone=True), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete=CASCADE_DELETE),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id', USER_ID_COLUMN, 'reaction_type')
    )
    op.create_index('idx_message_reactions_message_id', MESSAGE_REACTIONS_TABLE, ['message_id'])

    # === intensity_metrics ===
    op.create_table(
        INTENSITY_METRICS_TABLE,
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('entity_type', sa.VARCHAR(50), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('intensity_value', sa.Float(), nullable=False),
        sa.Column('metric_date', sa.Date(), nullable=False),
        sa.Column('note', sa.TEXT(), nullable=True),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(timezone=True), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_intensity_metrics_user_id', INTENSITY_METRICS_TABLE, [USER_ID_COLUMN])
    op.create_index('idx_intensity_metrics_entity', INTENSITY_METRICS_TABLE, ['entity_type', 'entity_id'])
    op.create_index('idx_intensity_metrics_date', INTENSITY_METRICS_TABLE, ['metric_date'])

    # === related_situations ===
    op.create_table(
        RELATED_SITUATIONS_TABLE,
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column(SOURCE_TYPE_COLUMN, sa.VARCHAR(50), nullable=False),
        sa.Column(SOURCE_ID_COLUMN, postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_type', sa.VARCHAR(50), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_title', sa.TEXT(), nullable=True),
        sa.Column('relation_type', sa.VARCHAR(50), nullable=False),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(timezone=True), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_related_situations_source', RELATED_SITUATIONS_TABLE, [SOURCE_TYPE_COLUMN, SOURCE_ID_COLUMN])
    op.create_index('idx_related_situations_user_id', RELATED_SITUATIONS_TABLE, [USER_ID_COLUMN])

    # === negative_impacts ===
    op.create_table(
        NEGATIVE_IMPACTS_TABLE,
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column(SOURCE_TYPE_COLUMN, sa.VARCHAR(50), nullable=False),
        sa.Column(SOURCE_ID_COLUMN, postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.TEXT(), nullable=False),
        sa.Column('description', sa.TEXT(), nullable=True),
        sa.Column('severity', sa.Integer(), nullable=True),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(timezone=True), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_negative_impacts_source', NEGATIVE_IMPACTS_TABLE, [SOURCE_TYPE_COLUMN, SOURCE_ID_COLUMN])
    op.create_index('idx_negative_impacts_user_id', NEGATIVE_IMPACTS_TABLE, [USER_ID_COLUMN])

    # === transformations ===
    op.create_table(
        TRANSFORMATIONS_TABLE,
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text(GEN_RANDOM_UUID_DEFAULT), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column(SOURCE_TYPE_COLUMN, sa.VARCHAR(50), nullable=False),
        sa.Column(SOURCE_ID_COLUMN, postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.TEXT(), nullable=False),
        sa.Column('description', sa.TEXT(), nullable=True),
        sa.Column('category', sa.VARCHAR(50), nullable=True),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(timezone=True), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_transformations_source', TRANSFORMATIONS_TABLE, [SOURCE_TYPE_COLUMN, SOURCE_ID_COLUMN])
    op.create_index('idx_transformations_user_id', TRANSFORMATIONS_TABLE, [USER_ID_COLUMN])


def downgrade() -> None:
    op.drop_table(TRANSFORMATIONS_TABLE)
    op.drop_table(NEGATIVE_IMPACTS_TABLE)
    op.drop_table(RELATED_SITUATIONS_TABLE)
    op.drop_table(INTENSITY_METRICS_TABLE)
    op.drop_table(MESSAGE_REACTIONS_TABLE)
    op.drop_table(MESSAGES_TABLE)
