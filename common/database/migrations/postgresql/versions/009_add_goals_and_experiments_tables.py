"""add goals and experiments tables

Revision ID: rev_011
Revises: 2bc25ccb3657
Create Date: 2026-05-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "rev_011"
down_revision: Union[str, None] = "2bc25ccb3657"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USER_ID_COLUMN = "user_id"
NOW_DEFAULT = "now()"
GEN_RANDOM_UUID_DEFAULT = "gen_random_uuid()"
USER_ID_FK = "user.id"
CASCADE_DELETE = "CASCADE"


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text(GEN_RANDOM_UUID_DEFAULT),
            nullable=False,
        ),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column("title", sa.VARCHAR(length=500), nullable=True),
        sa.Column("description", sa.TEXT(), nullable=False),
        sa.Column("status", sa.VARCHAR(length=50), server_default="active", nullable=False),
        sa.Column("priority", sa.VARCHAR(length=50), server_default="medium", nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("achieved_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_goals_user_id", "goals", [USER_ID_COLUMN], unique=False)
    op.create_index("idx_goals_status", "goals", ["status"], unique=False)

    op.create_table(
        "experiments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text(GEN_RANDOM_UUID_DEFAULT),
            nullable=False,
        ),
        sa.Column(USER_ID_COLUMN, sa.TEXT(), nullable=False),
        sa.Column("title", sa.VARCHAR(length=500), nullable=True),
        sa.Column("description", sa.TEXT(), nullable=False),
        sa.Column("status", sa.VARCHAR(length=50), server_default="active", nullable=False),
        sa.Column("success", sa.Integer(), server_default="0", nullable=False),
        sa.Column("outcome", sa.TEXT(), server_default="", nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text(NOW_DEFAULT), nullable=False),
        sa.ForeignKeyConstraint([USER_ID_COLUMN], [USER_ID_FK], ondelete=CASCADE_DELETE),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_experiments_user_id", "experiments", [USER_ID_COLUMN], unique=False)
    op.create_index("idx_experiments_status", "experiments", ["status"], unique=False)

    op.create_foreign_key(
        "fk_goal_threads_goal_id",
        "goal_threads",
        "goals",
        ["goal_id"],
        ["id"],
        ondelete=CASCADE_DELETE,
    )
    op.create_foreign_key(
        "fk_experiment_threads_experiment_id",
        "experiment_threads",
        "experiments",
        ["experiment_id"],
        ["id"],
        ondelete=CASCADE_DELETE,
    )


def downgrade() -> None:
    op.drop_constraint("fk_experiment_threads_experiment_id", "experiment_threads", type_="foreignkey")
    op.drop_constraint("fk_goal_threads_goal_id", "goal_threads", type_="foreignkey")
    op.drop_index("idx_experiments_status", table_name="experiments")
    op.drop_index("idx_experiments_user_id", table_name="experiments")
    op.drop_table("experiments")
    op.drop_index("idx_goals_status", table_name="goals")
    op.drop_index("idx_goals_user_id", table_name="goals")
    op.drop_table("goals")
