"""add beta_test table for beta signup form

Revision ID: 006_add_beta_test_table
Revises: 005_add_audio_fields_to_entries
Create Date: 2026-03-24

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'rev_008'
down_revision: str | None = 'rev_007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "beta_test",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("telegram", sa.TEXT(), nullable=False),
        sa.Column("email", sa.TEXT(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_beta_test_email", "beta_test", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_beta_test_email", table_name="beta_test")
    op.drop_table("beta_test")
