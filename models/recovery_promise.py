from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Index, Integer, Numeric, String, Text, column, text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins import UpdatedTimestampMixin


class RecoveryPromise(UpdatedTimestampMixin, Base):
    __tablename__ = "recovery_promises"

    __table_args__ = (
        Index(
            "idx_recovery_promises_application",
            column("application_id"),
            column("promise_status"),
            column("promise_date"),
        ),
        Index(
            "idx_recovery_promises_status_date",
            column("promise_status"),
            column("promise_date"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    promise_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    promise_date: Mapped[str] = mapped_column(Text, nullable=False)
    promise_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'active'")
    )
    commitment_notes: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    fulfilled_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    broken_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # created_at + updated_at via UpdatedTimestampMixin
