"""UnderwritingDecision ORM model — append-only snapshot of underwriting state at each decision.

application_id is INTEGER NOT NULL with no ForeignKey — preserving existing SQLite schema
behavior. No FK constraints exist on underwriting_decisions in the audited SQLite DDL.

This table is append-only. No updated_at column exists or should be added.
TimestampMixin provides created_at only.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Boolean, Index, Integer, String, Text, column, desc
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins import TimestampMixin


class UnderwritingDecision(TimestampMixin, Base):
    __tablename__ = "underwriting_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # application_id: plain INTEGER NOT NULL — no ForeignKey, preserving SQLite behavior
    application_id: Mapped[int] = mapped_column(Integer, nullable=False)

    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Underwriting dimension columns — all NOT NULL, matching SQLite DDL
    underwriting_status: Mapped[str] = mapped_column(String(32), nullable=False)
    affordability_assessment: Mapped[str] = mapped_column(String(32), nullable=False)
    repayment_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    business_stability_review: Mapped[str] = mapped_column(String(32), nullable=False)
    documentation_quality_review: Mapped[str] = mapped_column(String(32), nullable=False)

    # Observation and notes fields — NOT NULL DEFAULT ''
    operational_risk_observations: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    fraud_concern_observations: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=""
    )
    underwriting_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    decision_summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    decision_reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    escalation_reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    # reviewed_by remains TEXT string — not a FK to operators
    reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)

    # actor remains TEXT string — not a FK to operators
    actor: Mapped[str] = mapped_column(String(128), nullable=False)

    context_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    # INTEGER DEFAULT 0 → BOOLEAN DEFAULT false
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa.text("false")
    )

    # created_at provided by TimestampMixin (TIMESTAMPTZ NOT NULL DEFAULT now())
    # No updated_at — append-only table

    __table_args__ = (
        # Matches SQLite: (application_id, created_at DESC)
        # desc(column("created_at")) is the SQLAlchemy 2.x semantic pattern for DESC indexes
        Index(
            "idx_underwriting_decisions_application",
            "application_id",
            desc(column("created_at")),
        ),
    )
