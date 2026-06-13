from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, column, desc, text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    __table_args__ = (
        Index(
            "idx_application_documents_application",
            column("application_id"),
            column("document_type"),
            desc(column("uploaded_at")),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    cloudinary_url: Mapped[str] = mapped_column(Text, nullable=False)
    cloudinary_public_id: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
