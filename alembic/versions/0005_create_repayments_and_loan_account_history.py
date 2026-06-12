"""create repayments and loan_account_history

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-01 00:00:00.000000

Phase 3D — mirrors SQLite DDL from repositories/loans.py verbatim.

Type decisions confirmed by direct source inspection:

payment_date  → sa.Text()
    insert_repayment_record() accepts payment_date: str.
    SQLite index uses datetime(payment_date) for coercion, not native DATE.

issue_date    → sa.Text()
due_date      → sa.Text()
    Application writes '' (empty string) as sentinel value.
    Confirmed by TRIM(due_date) != '' guard in fetch_loan_portfolio_kpis().
    PostgreSQL Date cannot accept empty string.

Monetary columns  → Numeric(18, 2)  — eliminates REAL float imprecision.
repayment_progress → Numeric(5, 1)
is_critical        → BOOLEAN         — from SQLite INTEGER 0/1 (Phase 3C parity).
created_at         → TIMESTAMPTZ     — TimestampMixin standard.

No ForeignKey constraints anywhere.
Alembic indexes use sa.text("... DESC") exclusively.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "0005"
down_revision: str = "0004"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    # ------------------------------------------------------------------
    # repayments
    # ------------------------------------------------------------------
    op.create_table(
        "repayments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        # Text — application writes str; SQLite index coerces with datetime()
        sa.Column("payment_date", sa.Text(), nullable=False),
        sa.Column("payment_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("balance_before", sa.Numeric(18, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "repayment_notes",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_repayments_application",
        "repayments",
        [
            "application_id",
            sa.text("payment_date DESC"),
            sa.text("id DESC"),
        ],
    )

    # ------------------------------------------------------------------
    # loan_account_history
    # ------------------------------------------------------------------
    op.create_table(
        "loan_account_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("loan_lifecycle_status", sa.Text(), nullable=False),
        sa.Column(
            "loan_account_number",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("issued_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("outstanding_balance", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "repayment_progress",
            sa.Numeric(5, 1),
            nullable=False,
            server_default=sa.text("0"),
        ),
        # Text — application writes '' as sentinel; TRIM(due_date) != '' confirmed in source
        sa.Column("issue_date", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Text(), nullable=True),
        sa.Column("installment_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "repayment_frequency",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "collections_notes",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "missed_payment_observations",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "repayment_risk_level",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'current'"),
        ),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column(
            "context_notes",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "is_critical",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_loan_account_history_application",
        "loan_account_history",
        [
            "application_id",
            sa.text("created_at DESC"),
        ],
    )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------
def downgrade() -> None:
    op.drop_index(
        "idx_loan_account_history_application",
        table_name="loan_account_history",
    )
    op.drop_table("loan_account_history")

    op.drop_index("idx_repayments_application", table_name="repayments")
    op.drop_table("repayments")
