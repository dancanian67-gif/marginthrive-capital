from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Index, Integer, Numeric, String, Text, column, desc
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins import TimestampMixin


class Repayment(TimestampMixin, Base):
    """
    Immutable repayment ledger row.

    Mirrors the SQLite DDL from repositories/loans.py verbatim.

    Design notes:
    - No ForeignKey, no relationship() — application_id is a bare integer.
    - payment_date is Text, not Date.  insert_repayment_record() accepts
      payment_date: str and the SQLite index wraps it in datetime() for
      coercion.  Promoting to Date would break existing string inserts.
    - Monetary fields use Numeric(18, 2) to eliminate REAL float imprecision.
    - No updated_at — append-only table; TimestampMixin provides created_at only.
    """

    __tablename__ = "repayments"

    __table_args__ = (
        Index(
            "idx_repayments_application",
            column("application_id"),
            desc(column("payment_date")),
            desc(column("id")),
        ),
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Bare integer — no ForeignKey constraint, no relationship()
    application_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Batch identifier
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Date stored as application-formatted string — source: insert_repayment_record(payment_date: str)
    payment_date: Mapped[str] = mapped_column(Text, nullable=False)

    # Monetary fields — Numeric(18, 2) throughout
    payment_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    balance_before: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Notes
    repayment_notes: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )

    # Audit identity
    actor: Mapped[str] = mapped_column(Text, nullable=False)

    # created_at inherited from TimestampMixin — no updated_at
