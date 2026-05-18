"""Startup integrity and readiness checks (Phase D1)."""

import os
import sqlite3

from constants.app import DATABASE_PATH
from constants.ops import REQUIRED_DATABASE_TABLES
from repositories.database import get_db_connection
from repositories.operators import count_operators
from utils.env import validate_environment
from utils.ops_logging import log_operational_warning, log_startup


def run_startup_integrity_checks(*, log: bool = True) -> dict:
    """Validate environment and database readiness. Returns a structured status payload."""
    env_issues = validate_environment(strict=False)
    if log:
        for issue in env_issues:
            log_operational_warning("Startup configuration issue", issue=issue)

    database_ok = False
    tables_ok = False
    operator_count = 0
    database_error = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        database_ok = True

        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
        missing_tables = [name for name in REQUIRED_DATABASE_TABLES if name not in existing_tables]
        tables_ok = not missing_tables
        if missing_tables and log:
            log_operational_warning("Missing database tables", tables=",".join(missing_tables))

        operator_count = count_operators(cursor)
        conn.close()
    except (sqlite3.Error, OSError) as exc:
        database_error = str(exc)
        if log:
            log_operational_warning("Database readiness check failed", error=database_error)

    if operator_count == 0 and log:
        log_operational_warning(
            "No operator accounts found",
            hint="Set ADMIN_USERNAME and ADMIN_PASSWORD, then restart to bootstrap the first administrator.",
        )

    status = {
        "database_ok": database_ok,
        "tables_ok": tables_ok,
        "operator_count": operator_count,
        "env_issue_count": len(env_issues),
        "env_issues": env_issues,
        "database_error": database_error,
        "database_path": os.path.abspath(DATABASE_PATH),
    }
    status["ready"] = database_ok and tables_ok and not database_error
    if log:
        log_startup("Startup integrity checks completed", **{k: v for k, v in status.items() if k != "env_issues"})
    return status


def ensure_production_ready() -> None:
    """Fail fast when production configuration is unsafe."""
    validate_environment(strict=True)
