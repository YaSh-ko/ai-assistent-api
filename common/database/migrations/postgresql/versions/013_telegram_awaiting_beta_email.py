"""telegram_bot_subscribers: awaiting_beta_email for in-bot signup

Revision ID: rev_015
Revises: rev_014
Create Date: 2026-05-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "rev_015"
down_revision: Union[str, None] = "rev_014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "telegram_bot_subscribers",
        sa.Column(
            "awaiting_beta_email",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("telegram_bot_subscribers", "awaiting_beta_email")
