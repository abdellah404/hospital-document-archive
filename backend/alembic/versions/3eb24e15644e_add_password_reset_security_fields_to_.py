"""add password reset security fields to users

Revision ID: 3eb24e15644e
Revises: 07c1b5d7759e
Create Date: 2026-09-03 12:50:19.967743

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3eb24e15644e"
down_revision: Union[str, Sequence[str], None] = "07c1b5d7759e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.alter_column(
        "users",
        "must_change_password",
        existing_type=sa.Boolean(),
        server_default=None,
    )

    op.alter_column(
        "users",
        "token_version",
        existing_type=sa.Integer(),
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        "users",
        "token_version",
    )

    op.drop_column(
        "users",
        "must_change_password",
    )