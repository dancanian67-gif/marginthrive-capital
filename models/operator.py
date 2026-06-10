"""Operator account ORM model."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from constants.operators import OPERATOR_ROLES
from models.base import Base
from models.mixins import UpdatedTimestampMixin

_OPERATOR_ROLES_SQL = ", ".join(f"'{role}'" for role in OPERATOR_ROLES)


class Operator(UpdatedTimestampMixin, Base):
    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default="review_officer")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"role IN ({_OPERATOR_ROLES_SQL})",
            name="role",
        ),
        Index("ix_operators_active_username", "active", "username"),
    )
