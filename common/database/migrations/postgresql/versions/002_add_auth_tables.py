"""add auth tables (account and session)

Revision ID: 002_add_auth_tables
Revises: fcabe41820ab
Create Date: 2026-01-21 00:20:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'rev_004'
down_revision: str | None = 'rev_003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Constants for repeated string literals
USER_ID_COLUMN = 'user_id'
CREATED_AT_COLUMN = 'created_at'
NOW_DEFAULT = 'now()'
CASCADE_DELETE = 'CASCADE'
USER_ID_FK = 'user.id'
ACCOUNT_TABLE = 'account'
SESSION_TABLE = 'session'


def upgrade() -> None:
    # --- account table ---
    op.create_table(
        ACCOUNT_TABLE,
        sa.Column('id', sa.TEXT(), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('account_id', sa.TEXT(), nullable=False),
        sa.Column('provider_id', sa.VARCHAR(length=50), nullable=False),
        sa.Column('password', sa.TEXT(), nullable=True),
        sa.Column('access_token', sa.TEXT(), nullable=True),
        sa.Column('access_token_expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('refresh_token', sa.TEXT(), nullable=True),
        sa.Column('id_token', sa.TEXT(), nullable=True),
        sa.Column('scope', sa.TEXT(), nullable=True),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_id', 'account_id'),
    )
    op.create_index('idx_account_user_id', ACCOUNT_TABLE, [USER_ID_COLUMN], unique=False)
    op.create_index('idx_account_provider', ACCOUNT_TABLE, ['provider_id', 'account_id'], unique=False)

    # --- session table ---
    op.create_table(
        SESSION_TABLE,
        sa.Column('id', sa.TEXT(), nullable=False),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column('token', sa.TEXT(), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('ip_address', sa.VARCHAR(length=45), nullable=True),
        sa.Column('user_agent', sa.TEXT(), nullable=True),
        sa.Column(CREATED_AT_COLUMN, sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index('idx_session_user_id', SESSION_TABLE, [USER_ID_COLUMN], unique=False)
    op.create_index('idx_session_token', SESSION_TABLE, ['token'], unique=False)
    op.create_index('idx_session_expires_at', SESSION_TABLE, ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_session_expires_at', table_name=SESSION_TABLE)
    op.drop_index('idx_session_token', table_name=SESSION_TABLE)
    op.drop_index('idx_session_user_id', table_name=SESSION_TABLE)
    op.drop_table(SESSION_TABLE)
    
    op.drop_index('idx_account_provider', table_name=ACCOUNT_TABLE)
    op.drop_index('idx_account_user_id', table_name=ACCOUNT_TABLE)
    op.drop_table(ACCOUNT_TABLE)
