"""Alembic migration environment — uses DATABASE_MIGRATION_URL (direct PostgreSQL, port 5432)."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from db.config import ensure_sslmode, get_migration_database_url, normalize_database_url
from models.base import Base

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_migration_url() -> str:
    env_url = os.getenv("DATABASE_MIGRATION_URL", "").strip()
    if env_url:
        return ensure_sslmode(normalize_database_url(env_url))
    ini_url = config.get_main_option("sqlalchemy.url", "").strip()
    if ini_url:
        return ensure_sslmode(normalize_database_url(ini_url))
    return get_migration_database_url()


def run_migrations_offline() -> None:
    url = get_migration_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_migration_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
