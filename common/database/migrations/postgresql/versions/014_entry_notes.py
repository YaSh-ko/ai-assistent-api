"""entry_notes — append-only supplements to observations

Revision ID: rev_016
Revises: rev_015
Create Date: 2026-05-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "rev_016"
down_revision: Union[str, None] = "rev_015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entry_notes",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entry_id", UUID(as_uuid=True), sa.ForeignKey("entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(50), server_default="chat", nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_entry_notes_entry_id", "entry_notes", ["entry_id"])
    op.create_index("idx_entry_notes_user_id", "entry_notes", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_entry_notes_user_id", table_name="entry_notes")
    op.drop_index("idx_entry_notes_entry_id", table_name="entry_notes")
    op.drop_table("entry_notes")
