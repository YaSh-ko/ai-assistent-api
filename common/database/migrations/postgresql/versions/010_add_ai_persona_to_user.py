"""add ai_persona_tone and ai_persona_role to user

Revision ID: rev_012
Revises: rev_011
Create Date: 2026-05-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "rev_012"
down_revision: Union[str, None] = "rev_011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("ai_persona_tone", sa.TEXT(), nullable=True))
    op.add_column("user", sa.Column("ai_persona_role", sa.TEXT(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "ai_persona_role")
    op.drop_column("user", "ai_persona_tone")
