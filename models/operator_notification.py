from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Index, Integer, String, Text, column, desc, text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins import TimestampMixin


class OperatorNotification(TimestampMixin, Base):
    __tablename__ = "operator_notifications"

    __table_args__ = (
        Index(
            "idx_operator_notifications_target_unread",
            column("target_operator_id"),
            column("is_acknowledged"),
            column("severity"),
            desc(column("created_at")),
        ),
        Index(
            "idx_operator_notifications_application",
            column("application_id"),
            desc(column("created_at")),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_operator_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    event_category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'info'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    application_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    governance_tag: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    acknowledged_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # created_at via TimestampMixin — no updated_at
