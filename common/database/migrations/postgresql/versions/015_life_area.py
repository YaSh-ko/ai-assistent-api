"""life_area on entries and goals (detector theme)

Revision ID: rev_017
Revises: rev_016
Create Date: 2026-06-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "rev_017"
down_revision: Union[str, None] = "rev_016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "entries",
        sa.Column("life_area", sa.String(32), nullable=True),
    )
    op.add_column(
        "goals",
        sa.Column("life_area", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("goals", "life_area")
    op.drop_column("entries", "life_area")
