"""unify chat history with conversations table

Revision ID: 007_unify_chat_history
Revises: 006_add_beta_test_table
Create Date: 2026-04-01

"""
from typing import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'rev_009'
down_revision: str | None = 'rev_008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add history, context, and metadata to conversations
    op.add_column('conversations', sa.Column('history', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=True))
    op.add_column('conversations', sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True))
    op.add_column('conversations', sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True))


def downgrade() -> None:
    # Remove columns
    op.drop_column('conversations', 'metadata')
    op.drop_column('conversations', 'context')
    op.drop_column('conversations', 'history')
