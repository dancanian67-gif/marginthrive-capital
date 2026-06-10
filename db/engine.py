"""SQLAlchemy engine factory for application runtime (Supabase pooler)."""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from db.config import (
    DEFAULT_MAX_OVERFLOW,
    DEFAULT_POOL_SIZE,
    get_database_url,
    get_runtime_connect_args,
)


def create_application_engine(database_url: str | None = None) -> Engine:
    """Create a pooled engine for web workers. Uses DATABASE_URL when url is omitted."""
    url = database_url or get_database_url()
    return create_engine(
        url,
        poolclass=QueuePool,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=int(os.getenv("DATABASE_POOL_SIZE", str(DEFAULT_POOL_SIZE))),
        max_overflow=int(os.getenv("DATABASE_MAX_OVERFLOW", str(DEFAULT_MAX_OVERFLOW))),
        connect_args=get_runtime_connect_args(),
        future=True,
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-scoped application engine (connection pool, not a session)."""
    return create_application_engine()
