"""Create workflow_history and underwriting_decisions tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-11

Both tables are append-only audit trails.
application_id is INTEGER NOT NULL with no foreign key — preserving existing SQLite behavior.
No ForeignKey constraints are introduced in this migration.

Index naming: preserves legacy SQLite idx_* names exactly.
DESC indexes use desc(column("created_at")) — the SQLAlchemy 2.x semantic pattern.
Generates: ON table_name (application_id, created_at DESC)
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import column, desc

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- workflow_history ---
    op.create_table(
        "workflow_history",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), primary_key=True),
        # application_id: INTEGER NOT NULL — no ForeignKey
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        # Nullable columns — match SQLite DDL exactly
        sa.Column("field_name", sa.String(length=64), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        # JSON snapshots stored as TEXT
        sa.Column("previous_state", sa.Text(), nullable=False),
        sa.Column("new_state", sa.Text(), nullable=False),
        # actor: TEXT string — not a FK
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("context_notes", sa.Text(), server_default="", nullable=False),
        # is_critical: INTEGER DEFAULT 0 → BOOLEAN DEFAULT false
        sa.Column(
            "is_critical",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        # Nullable — match SQLite DDL exactly
        sa.Column("transition_warning", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Composite descending index — matches SQLite: (application_id, created_at DESC)
    # desc(column("created_at")) generates: ON workflow_history (application_id, created_at DESC)
    op.create_index(
        "idx_workflow_history_application",
        "workflow_history",
        ["application_id", desc(column("created_at"))],
    )
    # Simple index on batch_id
    op.create_index(
        "idx_workflow_history_batch",
        "workflow_history",
        ["batch_id"],
    )

    # --- underwriting_decisions ---
    op.create_table(
        "underwriting_decisions",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), primary_key=True),
        # application_id: INTEGER NOT NULL — no ForeignKey
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        # Underwriting dimension columns — all NOT NULL
        sa.Column("underwriting_status", sa.String(length=32), nullable=False),
        sa.Column("affordability_assessment", sa.String(length=32), nullable=False),
        sa.Column("repayment_confidence", sa.String(length=32), nullable=False),
        sa.Column("business_stability_review", sa.String(length=32), nullable=False),
        sa.Column("documentation_quality_review", sa.String(length=32), nullable=False),
        # Observation and notes — NOT NULL DEFAULT ''
        sa.Column(
            "operational_risk_observations", sa.Text(), server_default="", nullable=False
        ),
        sa.Column(
            "fraud_concern_observations", sa.Text(), server_default="", nullable=False
        ),
        sa.Column("underwriting_notes", sa.Text(), server_default="", nullable=False),
        sa.Column("decision_summary", sa.Text(), server_default="", nullable=False),
        sa.Column("decision_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("escalation_reason", sa.Text(), server_default="", nullable=False),
        # reviewed_by: TEXT string — not a FK
        sa.Column("reviewed_by", sa.String(length=128), nullable=False),
        # actor: TEXT string — not a FK
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("context_notes", sa.Text(), server_default="", nullable=False),
        # is_critical: INTEGER DEFAULT 0 → BOOLEAN DEFAULT false
        sa.Column(
            "is_critical",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Composite descending index — matches SQLite: (application_id, created_at DESC)
    # desc(column("created_at")) generates:
    # ON underwriting_decisions (application_id, created_at DESC)
    op.create_index(
        "idx_underwriting_decisions_application",
        "underwriting_decisions",
        ["application_id", desc(column("created_at"))],
    )


def downgrade() -> None:
    # Drop indexes before tables
    op.drop_index(
        "idx_underwriting_decisions_application",
        table_name="underwriting_decisions",
    )
    op.drop_table("underwriting_decisions")

    op.drop_index("idx_workflow_history_batch", table_name="workflow_history")
    op.drop_index(
        "idx_workflow_history_application",
        table_name="workflow_history",
    )
    op.drop_table("workflow_history")
