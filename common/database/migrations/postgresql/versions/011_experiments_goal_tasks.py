"""experiments: goal_id, phase, due_date, source for goal tasks

Revision ID: rev_013
Revises: rev_012
Create Date: 2026-05-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "rev_013"
down_revision: Union[str, None] = "rev_012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "experiments",
        sa.Column("phase", sa.VARCHAR(length=20), server_default="now", nullable=False),
    )
    op.add_column(
        "experiments",
        sa.Column("due_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "experiments",
        sa.Column("source", sa.VARCHAR(length=20), server_default="user", nullable=False),
    )
    op.create_foreign_key(
        "fk_experiments_goal_id",
        "experiments",
        "goals",
        ["goal_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_experiments_goal_id", "experiments", ["goal_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_experiments_goal_id", table_name="experiments")
    op.drop_constraint("fk_experiments_goal_id", "experiments", type_="foreignkey")
    op.drop_column("experiments", "source")
    op.drop_column("experiments", "due_date")
    op.drop_column("experiments", "phase")
    op.drop_column("experiments", "goal_id")
