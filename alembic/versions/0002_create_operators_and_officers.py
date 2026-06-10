"""Create operators and officers tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-10

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import CITEXT

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OPERATOR_ROLES = (
    "administrator",
    "review_officer",
    "analyst",
    "operations_manager",
)
_OPERATOR_ROLES_SQL = ", ".join(f"'{role}'" for role in _OPERATOR_ROLES)


def upgrade() -> None:
    op.create_table(
        "operators",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), primary_key=True),
        sa.Column("username", CITEXT(), nullable=False),
        sa.Column("email", CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), server_default="", nullable=False),
        sa.Column("role", sa.String(length=32), server_default="review_officer", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("username", name="uq_operators_username"),
        sa.UniqueConstraint("email", name="uq_operators_email"),
        sa.CheckConstraint(
            f"role IN ({_OPERATOR_ROLES_SQL})",
            name="ck_operators_role",
        ),
    )
    op.create_index("ix_operators_active_username", "operators", ["active", "username"])

    op.create_table(
        "officers",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), primary_key=True),
        sa.Column("name", CITEXT(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_officers_name"),
    )


def downgrade() -> None:
    op.drop_table("officers")
    op.drop_table("operators")
