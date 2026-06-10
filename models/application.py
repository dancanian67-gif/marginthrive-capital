"""Loan application ORM model — wide aggregate of intake, workflow, underwriting, loan, and collections state.

Index naming: this table intentionally preserves legacy SQLite ``idx_applications_*`` index
names instead of the metadata convention ``ix_*`` prefix. Startup validation in
``constants/ops.py`` (``PERFORMANCE_INDEX_NAMES``) and ``utils/startup.py`` expect
these exact names; do not rename to ``ix_applications_*`` without updating those checks.

No foreign keys or ORM relationships — ``assigned_officer`` and ``collections_assigned_to``
are TEXT name fields (soft links), matching the existing SQLite schema.

Nullable columns use ``Mapped[X | None]`` per SQLAlchemy 2.x typing conventions (nullable
is inferred from the union). Deployment target is Python 3.12.8 (``runtime.txt``).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins import UpdatedTimestampMixin


class Application(UpdatedTimestampMixin, Base):
    __tablename__ = "applications"

    # --- Identity / intake ---
    id: Mapped[int] = mapped_column(primary_key=True)
    business_name: Mapped[str] = mapped_column(String(150), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    product: Mapped[str] = mapped_column(String(64), nullable=False)

    # --- Workflow ---
    status: Mapped[str] = mapped_column(String(64), nullable=False, server_default="New applicant")
    sub_status: Mapped[str | None] = mapped_column(String(64))
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, server_default="Unassigned")
    approval_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    assigned_officer: Mapped[str] = mapped_column(String(150), nullable=False, server_default="")
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, server_default="")
    business_type: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(32), nullable=False, server_default="")
    flagged_fraud: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    loan_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    # --- Underwriting (current state) ---
    underwriting_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending_review"
    )
    affordability_assessment: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="not_assessed"
    )
    repayment_confidence: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="not_assessed"
    )
    business_stability_review: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="not_assessed"
    )
    documentation_quality_review: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="not_assessed"
    )
    operational_risk_observations: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    fraud_concern_observations: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    underwriting_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    decision_summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    decision_reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False, server_default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalation_reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    # --- Loan servicing (current state) ---
    loan_lifecycle_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="not_issued"
    )
    loan_account_number: Mapped[str] = mapped_column(String(32), nullable=False, server_default="")
    issued_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    outstanding_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    repayment_progress: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), nullable=False, server_default=sa.text("0")
    )
    issue_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    installment_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    repayment_frequency: Mapped[str] = mapped_column(String(16), nullable=False, server_default="")
    collections_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    missed_payment_observations: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    repayment_risk_level: Mapped[str] = mapped_column(String(16), nullable=False, server_default="current")
    last_payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Collections (current state) ---
    collections_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="not_in_collections"
    )
    collections_priority: Mapped[str] = mapped_column(String(16), nullable=False, server_default="normal")
    collections_assigned_to: Mapped[str] = mapped_column(String(150), nullable=False, server_default="")
    collections_last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collections_next_follow_up: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collections_notes_summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    collections_risk_level: Mapped[str] = mapped_column(String(16), nullable=False, server_default="routine")

    # created_at, updated_at — from UpdatedTimestampMixin (TIMESTAMPTZ NOT NULL)

    __table_args__ = (
        # Legacy idx_* names preserved for PERFORMANCE_INDEX_NAMES / startup checks.
        # Do NOT rename to ix_applications_* without updating constants/ops.py and utils/startup.py.
        Index("idx_applications_created_at", "created_at"),
        Index("idx_applications_status", "status"),
        Index("idx_applications_risk_level", "risk_level"),
        Index("idx_applications_assigned_officer", "assigned_officer"),
        Index("idx_applications_underwriting_status", "underwriting_status"),
        Index("idx_applications_loan_lifecycle_status", "loan_lifecycle_status"),
        Index("idx_applications_reviewed_at", "reviewed_at"),
        Index("idx_applications_collections_status", "collections_status"),
        Index("idx_applications_collections_assigned", "collections_assigned_to"),
        Index("idx_applications_collections_follow_up", "collections_next_follow_up"),
    )
