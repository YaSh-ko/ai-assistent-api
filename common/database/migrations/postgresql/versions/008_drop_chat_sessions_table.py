"""drop chat sessions table

Revision ID: 008_drop_chat_sessions_table
Revises: 007_unify_chat_history
Create Date: 2026-04-01

"""
from typing import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'rev_010'
down_revision: str | None = 'rev_009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop indices and table
    op.drop_index('idx_chat_sessions_updated_at', table_name='chat_sessions')
    op.drop_index('idx_chat_sessions_user_id', table_name='chat_sessions')
    op.drop_table('chat_sessions')


def downgrade() -> None:
    # Recreate table as it was in migration 004
    op.create_table(
        'chat_sessions',
        sa.Column('session_id', sa.VARCHAR(length=255), nullable=False),
        sa.Column('user_id', sa.VARCHAR(length=255), nullable=False),
        sa.Column('status', sa.VARCHAR(length=50), server_default='active', nullable=False),
        sa.Column('history', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('session_id')
    )
    op.create_index('idx_chat_sessions_user_id', 'chat_sessions', ['user_id'], unique=False)
    op.create_index('idx_chat_sessions_updated_at', 'chat_sessions', ['updated_at'], unique=False)
