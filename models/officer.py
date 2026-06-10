"""Loan officer name registry ORM model."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Boolean
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.mixins import TimestampMixin


class Officer(TimestampMixin, Base):
    __tablename__ = "officers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
