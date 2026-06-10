"""Create applications table (wide aggregate — intake through collections).

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-10

Index naming: preserves legacy SQLite ``idx_applications_*`` names for compatibility
with ``constants/ops.py`` ``PERFORMANCE_INDEX_NAMES`` and startup validation in
``utils/startup.py``. Do not rename to ``ix_applications_*`` without updating those checks.

No foreign keys — ``assigned_officer`` and ``collections_assigned_to`` remain TEXT fields.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), primary_key=True),
        # Identity / intake
        sa.Column("business_name", sa.String(length=150), nullable=False),
        sa.Column("owner_name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("revenue", sa.Numeric(18, 2), nullable=False),
        sa.Column("product", sa.String(length=64), nullable=False),
        # Workflow
        sa.Column("status", sa.String(length=64), server_default="New applicant", nullable=False),
        sa.Column("sub_status", sa.String(length=64), nullable=True),
        sa.Column("risk_level", sa.String(length=32), server_default="Unassigned", nullable=False),
        sa.Column("approval_notes", sa.Text(), server_default="", nullable=False),
        sa.Column("assigned_officer", sa.String(length=150), server_default="", nullable=False),
        sa.Column("phone_number", sa.String(length=20), server_default="", nullable=False),
        sa.Column("business_type", sa.String(length=64), server_default="", nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=32), server_default="", nullable=False),
        sa.Column("flagged_fraud", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("loan_amount", sa.Numeric(18, 2), nullable=True),
        # Underwriting (current state)
        sa.Column(
            "underwriting_status",
            sa.String(length=32),
            server_default="pending_review",
            nullable=False,
        ),
        sa.Column(
            "affordability_assessment",
            sa.String(length=32),
            server_default="not_assessed",
            nullable=False,
        ),
        sa.Column(
            "repayment_confidence",
            sa.String(length=32),
            server_default="not_assessed",
            nullable=False,
        ),
        sa.Column(
            "business_stability_review",
            sa.String(length=32),
            server_default="not_assessed",
            nullable=False,
        ),
        sa.Column(
            "documentation_quality_review",
            sa.String(length=32),
            server_default="not_assessed",
            nullable=False,
        ),
        sa.Column("operational_risk_observations", sa.Text(), server_default="", nullable=False),
        sa.Column("fraud_concern_observations", sa.Text(), server_default="", nullable=False),
        sa.Column("underwriting_notes", sa.Text(), server_default="", nullable=False),
        sa.Column("decision_summary", sa.Text(), server_default="", nullable=False),
        sa.Column("decision_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("reviewed_by", sa.String(length=128), server_default="", nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_reason", sa.Text(), server_default="", nullable=False),
        # Loan servicing (current state)
        sa.Column(
            "loan_lifecycle_status",
            sa.String(length=32),
            server_default="not_issued",
            nullable=False,
        ),
        sa.Column("loan_account_number", sa.String(length=32), server_default="", nullable=False),
        sa.Column("issued_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("outstanding_balance", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "repayment_progress",
            sa.Numeric(5, 1),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("installment_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("repayment_frequency", sa.String(length=16), server_default="", nullable=False),
        sa.Column("collections_notes", sa.Text(), server_default="", nullable=False),
        sa.Column("missed_payment_observations", sa.Text(), server_default="", nullable=False),
        sa.Column("repayment_risk_level", sa.String(length=16), server_default="current", nullable=False),
        sa.Column("last_payment_at", sa.DateTime(timezone=True), nullable=True),
        # Collections (current state)
        sa.Column(
            "collections_status",
            sa.String(length=32),
            server_default="not_in_collections",
            nullable=False,
        ),
        sa.Column("collections_priority", sa.String(length=16), server_default="normal", nullable=False),
        sa.Column("collections_assigned_to", sa.String(length=150), server_default="", nullable=False),
        sa.Column("collections_last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collections_next_follow_up", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collections_notes_summary", sa.Text(), server_default="", nullable=False),
        sa.Column("collections_risk_level", sa.String(length=16), server_default="routine", nullable=False),
        # Timestamps (managed by UpdatedTimestampMixin in ORM)
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
    )

    # Legacy idx_* names — see module docstring.
    op.create_index("idx_applications_created_at", "applications", ["created_at"])
    op.create_index("idx_applications_status", "applications", ["status"])
    op.create_index("idx_applications_risk_level", "applications", ["risk_level"])
    op.create_index("idx_applications_assigned_officer", "applications", ["assigned_officer"])
    op.create_index("idx_applications_underwriting_status", "applications", ["underwriting_status"])
    op.create_index("idx_applications_loan_lifecycle_status", "applications", ["loan_lifecycle_status"])
    op.create_index("idx_applications_reviewed_at", "applications", ["reviewed_at"])
    op.create_index("idx_applications_collections_status", "applications", ["collections_status"])
    op.create_index("idx_applications_collections_assigned", "applications", ["collections_assigned_to"])
    op.create_index(
        "idx_applications_collections_follow_up",
        "applications",
        ["collections_next_follow_up"],
    )


def downgrade() -> None:
    op.drop_index("idx_applications_collections_follow_up", table_name="applications")
    op.drop_index("idx_applications_collections_assigned", table_name="applications")
    op.drop_index("idx_applications_collections_status", table_name="applications")
    op.drop_index("idx_applications_reviewed_at", table_name="applications")
    op.drop_index("idx_applications_loan_lifecycle_status", table_name="applications")
    op.drop_index("idx_applications_underwriting_status", table_name="applications")
    op.drop_index("idx_applications_assigned_officer", table_name="applications")
    op.drop_index("idx_applications_risk_level", table_name="applications")
    op.drop_index("idx_applications_status", table_name="applications")
    op.drop_index("idx_applications_created_at", table_name="applications")
    op.drop_table("applications")
