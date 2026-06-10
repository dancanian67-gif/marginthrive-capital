"""Database URL resolution for application runtime and Alembic migrations."""

from __future__ import annotations

import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

DEFAULT_POOL_SIZE = 2
DEFAULT_MAX_OVERFLOW = 3
DEFAULT_SSLMODE = "require"


def normalize_database_url(url: str) -> str:
    """Normalize Supabase/Heroku-style URLs for SQLAlchemy + psycopg2."""
    normalized = url.strip()
    if normalized.startswith("postgres://"):
        return normalized.replace("postgres://", "postgresql+psycopg2://", 1)
    if normalized.startswith("postgresql://") and "+psycopg2" not in normalized:
        return normalized.replace("postgresql://", "postgresql+psycopg2://", 1)
    return normalized


def ensure_sslmode(url: str, *, mode: str | None = None) -> str:
    """Append sslmode when absent. Override via DATABASE_SSLMODE or an explicit URL param."""
    sslmode = (mode or os.getenv("DATABASE_SSLMODE", DEFAULT_SSLMODE)).strip()
    if not sslmode:
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" in query:
        return url
    query["sslmode"] = sslmode
    return urlunparse(parsed._replace(query=urlencode(query)))


def get_runtime_connect_args() -> dict:
    """psycopg2 connect_args for Supabase transaction pooler (port 6543).

    prepare_threshold=0 disables server-side prepared statements, which are
    incompatible with PgBouncer/Supavisor transaction pooling mode.
    """
    return {"prepare_threshold": 0}


def database_url_configured() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip())


def migration_database_url_configured() -> bool:
    return bool(os.getenv("DATABASE_MIGRATION_URL", "").strip())


def get_database_url() -> str:
    """Supabase pooler URL (port 6543) for application runtime."""
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is not set. Use the Supabase connection pooler URL (port 6543) for runtime."
        )
    return ensure_sslmode(normalize_database_url(raw))


def get_migration_database_url() -> str:
    """Direct PostgreSQL URL (port 5432) for Alembic migrations."""
    raw = os.getenv("DATABASE_MIGRATION_URL", "").strip()
    if not raw:
        raise RuntimeError(
            "DATABASE_MIGRATION_URL is not set. Use the Supabase direct connection URL (port 5432) for migrations."
        )
    return ensure_sslmode(normalize_database_url(raw))
