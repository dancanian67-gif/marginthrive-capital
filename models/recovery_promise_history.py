from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Index, Integer, Numeric, String, Text, column, desc, text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins import TimestampMixin


class RecoveryPromiseHistory(TimestampMixin, Base):
    __tablename__ = "recovery_promise_history"

    __table_args__ = (
        Index(
            "idx_recovery_promise_history_promise",
            column("promise_id"),
            desc(column("created_at")),
        ),
        Index(
            "idx_recovery_promise_history_application",
            column("application_id"),
            desc(column("created_at")),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promise_id: Mapped[int] = mapped_column(Integer, nullable=False)
    application_id: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    promise_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    promise_date: Mapped[str] = mapped_column(Text, nullable=False)
    promise_status: Mapped[str] = mapped_column(String(32), nullable=False)
    commitment_notes: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    action_type: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'promise_update'")
    )
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    context_notes: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # created_at via TimestampMixin — no updated_at
