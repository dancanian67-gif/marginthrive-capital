"""Reusable timestamp columns for ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Single created_at column with a database default."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class UpdatedTimestampMixin(TimestampMixin):
    """created_at + updated_at.

    updated_at is ORM-managed via onupdate=func.now() and is not refreshed by
    raw SQL UPDATE statements outside the SQLAlchemy session.
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
