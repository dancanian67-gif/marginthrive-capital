"""phase 3f operational notifications and documents

Revision ID: 0007
Revises: 0006
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- operational_events ---------------------------------------------------
    op.create_table(
        "operational_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_category", sa.String(length=64), nullable=False),
        sa.Column(
            "severity",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'info'"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("governance_tag", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_operational_events_category_created",
        "operational_events",
        ["event_category", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_operational_events_application",
        "operational_events",
        ["application_id", sa.text("created_at DESC")],
    )

    # --- operator_notifications -----------------------------------------------
    op.create_table(
        "operator_notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("target_operator_id", sa.Integer(), nullable=True),
        sa.Column("event_category", sa.String(length=64), nullable=False),
        sa.Column(
            "severity",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'info'"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("governance_tag", sa.Text(), nullable=True),
        sa.Column(
            "is_acknowledged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("acknowledged_at", sa.Text(), nullable=True),
        sa.Column("acknowledged_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_operator_notifications_target_unread",
        "operator_notifications",
        [
            "target_operator_id",
            "is_acknowledged",
            "severity",
            sa.text("created_at DESC"),
        ],
    )
    op.create_index(
        "idx_operator_notifications_application",
        "operator_notifications",
        ["application_id", sa.text("created_at DESC")],
    )

    # --- application_documents ------------------------------------------------
    op.create_table(
        "application_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("cloudinary_url", sa.Text(), nullable=False),
        sa.Column("cloudinary_public_id", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.Text(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_application_documents_application",
        "application_documents",
        ["application_id", "document_type", sa.text("uploaded_at DESC")],
    )


def downgrade() -> None:
    # Drop indexes before tables.
    # Table drop order: application_documents → operator_notifications → operational_events

    # --- application_documents ------------------------------------------------
    op.drop_index(
        "idx_application_documents_application",
        table_name="application_documents",
    )
    op.drop_table("application_documents")

    # --- operator_notifications -----------------------------------------------
    op.drop_index(
        "idx_operator_notifications_application",
        table_name="operator_notifications",
    )
    op.drop_index(
        "idx_operator_notifications_target_unread",
        table_name="operator_notifications",
    )
    op.drop_table("operator_notifications")

    # --- operational_events ---------------------------------------------------
    op.drop_index(
        "idx_operational_events_application",
        table_name="operational_events",
    )
    op.drop_index(
        "idx_operational_events_category_created",
        table_name="operational_events",
    )
    op.drop_table("operational_events")
