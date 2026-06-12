from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Index, Integer, String, Text, column, desc, text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins import TimestampMixin


class CollectionsHistory(TimestampMixin, Base):
    __tablename__ = "collections_history"

    __table_args__ = (
        Index(
            "idx_collections_history_application",
            column("application_id"),
            desc(column("created_at")),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    collections_status: Mapped[str] = mapped_column(String(32), nullable=False)
    collections_priority: Mapped[str] = mapped_column(String(32), nullable=False)
    collections_assigned_to: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    collections_last_contact_at: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    collections_next_follow_up: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    collections_notes_summary: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    collections_risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    action_type: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'collections_update'")
    )
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    context_notes: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # created_at via TimestampMixin — no updated_at
