"""create collections and recovery promise tables

Revision ID: 0006
Revises: 0005
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- collections_history ---------------------------------------------------
    op.create_table(
        "collections_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("collections_status", sa.String(length=32), nullable=False),
        sa.Column("collections_priority", sa.String(length=32), nullable=False),
        sa.Column(
            "collections_assigned_to",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("collections_last_contact_at", sa.Text(), nullable=True),
        sa.Column("collections_next_follow_up", sa.Text(), nullable=True),
        sa.Column(
            "collections_notes_summary",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("collections_risk_level", sa.String(length=32), nullable=False),
        sa.Column(
            "action_type",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'collections_update'"),
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
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_collections_history_application",
        "collections_history",
        ["application_id", sa.text("created_at DESC")],
    )

    # --- recovery_promises -----------------------------------------------------
    op.create_table(
        "recovery_promises",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("promise_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("promise_date", sa.Text(), nullable=False),
        sa.Column(
            "promise_status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "commitment_notes",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("fulfilled_at", sa.Text(), nullable=True),
        sa.Column("broken_at", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_recovery_promises_application",
        "recovery_promises",
        ["application_id", "promise_status", "promise_date"],
    )
    op.create_index(
        "idx_recovery_promises_status_date",
        "recovery_promises",
        ["promise_status", "promise_date"],
    )

    # --- recovery_promise_history ----------------------------------------------
    op.create_table(
        "recovery_promise_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("promise_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("promise_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("promise_date", sa.Text(), nullable=False),
        sa.Column("promise_status", sa.String(length=32), nullable=False),
        sa.Column(
            "commitment_notes",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "action_type",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'promise_update'"),
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
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_recovery_promise_history_promise",
        "recovery_promise_history",
        ["promise_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_recovery_promise_history_application",
        "recovery_promise_history",
        ["application_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    # Drop indexes before tables; reverse creation order: RPH → RP → CH

    # --- recovery_promise_history ----------------------------------------------
    op.drop_index(
        "idx_recovery_promise_history_application",
        table_name="recovery_promise_history",
    )
    op.drop_index(
        "idx_recovery_promise_history_promise",
        table_name="recovery_promise_history",
    )
    op.drop_table("recovery_promise_history")

    # --- recovery_promises -----------------------------------------------------
    op.drop_index(
        "idx_recovery_promises_status_date",
        table_name="recovery_promises",
    )
    op.drop_index(
        "idx_recovery_promises_application",
        table_name="recovery_promises",
    )
    op.drop_table("recovery_promises")

    # --- collections_history ---------------------------------------------------
    op.drop_index(
        "idx_collections_history_application",
        table_name="collections_history",
    )
    op.drop_table("collections_history")
