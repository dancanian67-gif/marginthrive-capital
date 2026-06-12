from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Index, Integer, Numeric, String, Text, column, desc
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins import TimestampMixin

class LoanAccountHistory(TimestampMixin, Base):
    """
    Immutable audit snapshot of a loan account state at a point in time.

    Mirrors the SQLite DDL from repositories/loans.py,
    init_loan_account_history_table(), verbatim.

    Design notes:
    - No ForeignKey, no relationship() — application_id is a bare integer.
    - issue_date and due_date are Text, not Date.  The application writes ''
      (empty string) as a sentinel value — confirmed by TRIM(due_date) != ''
      guard in fetch_loan_portfolio_kpis().  A Date column cannot accept ''.
    - loan_account_number VARCHAR(64), repayment_frequency VARCHAR(32), and
      repayment_risk_level VARCHAR(32) widths confirmed by Phase 3B parity
      with applications table and by SQLite DDL in this file.
    - is_critical maps INTEGER 0/1 → BOOLEAN, consistent with Phase 3C.
    - No updated_at — append-only table; TimestampMixin provides created_at only.
    """

    __tablename__ = "loan_account_history"

    __table_args__ = (
        Index(
            "idx_loan_account_history_application",
            column("application_id"),
            desc(column("created_at")),
        ),
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Bare integer — no ForeignKey constraint, no relationship()
    application_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Batch identifier
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Lifecycle state label
    loan_lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False)

    # Snapshot of applications.loan_account_number — VARCHAR(64) by Phase 3B parity
    loan_account_number: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=""
    )

    # Monetary snapshots — Numeric(18, 2)
    issued_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    outstanding_balance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )

    # Repayment progress percentage — Numeric(5, 1) e.g. 99.9
    repayment_progress: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), nullable=False, server_default="0"
    )

    # Date-like fields stored as application-formatted strings.
    # The application writes '' (empty string) as a sentinel — confirmed by
    # TRIM(due_date) != '' guard in fetch_loan_portfolio_kpis().
    # Promoting to Date would break inserts containing ''.
    issue_date: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_date: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optional monetary
    installment_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), nullable=True
    )

    # Snapshot of applications.repayment_frequency — VARCHAR(32) by Phase 3B parity
    repayment_frequency: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=""
    )

    # Narrative fields
    collections_notes: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    missed_payment_observations: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )

    # Snapshot of applications.repayment_risk_level — VARCHAR(32), default 'current'
    repayment_risk_level: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="current"
    )

    # Audit identity
    actor: Mapped[str] = mapped_column(Text, nullable=False)

    # Free-form context at snapshot time
    context_notes: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )

    # Critical flag — INTEGER 0/1 in SQLite → BOOLEAN in PostgreSQL
    # Consistent with WorkflowHistory.is_critical mapping from Phase 3C
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # created_at inherited from TimestampMixin — no updated_at
