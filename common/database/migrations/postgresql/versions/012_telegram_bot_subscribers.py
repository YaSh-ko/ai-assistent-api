"""telegram_bot_subscribers for beta-test Telegram confirmations

Revision ID: rev_014
Revises: rev_013
Create Date: 2026-05-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "rev_014"
down_revision: Union[str, None] = "rev_013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_bot_subscribers",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.TEXT(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("chat_id"),
    )
    op.create_index(
        "idx_telegram_bot_subscribers_username",
        "telegram_bot_subscribers",
        ["telegram_username"],
        unique=True,
        postgresql_where=sa.text("telegram_username IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_telegram_bot_subscribers_username", table_name="telegram_bot_subscribers")
    op.drop_table("telegram_bot_subscribers")
