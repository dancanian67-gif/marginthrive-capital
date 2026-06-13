"""WorkflowHistory ORM model — append-only audit trail of field-level application changes.

application_id is INTEGER NOT NULL with no ForeignKey — preserving existing SQLite schema
behavior. No FK constraints exist on workflow_history in the audited SQLite DDL.

This table is append-only. No updated_at column exists or should be added.
TimestampMixin provides created_at only.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Boolean, Index, Integer, String, Text, column, desc
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins import TimestampMixin


class WorkflowHistory(TimestampMixin, Base):
    __tablename__ = "workflow_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(64))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    previous_state: Mapped[str] = mapped_column(Text, nullable=False)
    new_state: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    context_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )
    transition_warning: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "idx_workflow_history_application",
            "application_id",
            desc(column("created_at")),
        ),
        Index("idx_workflow_history_batch", "batch_id"),
    )