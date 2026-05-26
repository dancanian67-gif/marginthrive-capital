"""Startup integrity and readiness checks (Phase D1, E2)."""

import os
import sqlite3

from constants.app import DATABASE_PATH
from constants.ops import (
    DEFAULT_BACKUP_DIR,
    PERFORMANCE_INDEX_NAMES,
    REQUIRED_DATABASE_TABLES,
    STARTUP_OPTIONAL_DIRS,
)
from repositories.database import fetch_sqlite_journal_mode, get_db_connection
from repositories.indexes import verify_performance_indexes
from constants.operators import OPERATOR_ROLES
from repositories.governance_validation import (
    count_orphaned_underwriting_decisions,
    count_orphaned_workflow_history,
    fetch_invalid_operator_roles,
    fetch_operator_role_counts,
)
from repositories.operators import count_active_administrators, count_operators
from utils.env import validate_environment
from utils.governance import warn_orphaned_governance_references
from utils.integrity_checks import run_operational_integrity_checks
from utils.ops_logging import log_operational_warning, log_startup
from utils.resilience import warn_backup_directory_unavailable, warn_missing_directory

MAX_INACTIVE_OPERATORS_WARN = 10


def _ensure_optional_directories(*, log: bool) -> list[str]:
    issues: list[str] = []
    for dirname in STARTUP_OPTIONAL_DIRS:
        path = os.path.abspath(os.getenv("BACKUP_DIR", dirname) if dirname == "backups" else dirname)
        if os.path.isdir(path):
            continue
        parent = os.path.dirname(path) or "."
        if os.path.isdir(parent) and os.access(parent, os.W_OK):
            try:
                os.makedirs(path, exist_ok=True)
                if log:
                    log_startup("Created optional directory", path=path)
            except OSError as exc:
                issues.append(f"Could not create directory {path}: {exc}")
                if log:
                    warn_missing_directory(path, purpose="optional operational storage")
        else:
            issues.append(f"Optional directory missing and not creatable: {path}")
            if log:
                warn_missing_directory(path, purpose="optional operational storage")
    return issues


def _validate_backup_path(*, log: bool) -> bool:
    backup_dir = os.path.abspath(os.getenv("BACKUP_DIR", DEFAULT_BACKUP_DIR))
    if os.path.isdir(backup_dir) and os.access(backup_dir, os.W_OK):
        return True
    if log:
        warn_backup_directory_unavailable(
            backup_dir,
            error="Directory missing or not writable",
        )
    return False


def _operator_sanity_checks(cursor, *, log: bool) -> dict:
    cursor.execute("SELECT COUNT(*) AS total FROM operators WHERE active = 1")
    active_count = cursor.fetchone()["total"] or 0
    admin_count = count_active_administrators(cursor)
    duplicate_usernames = 0
    cursor.execute(
        """
        SELECT COUNT(*) AS duplicate_count FROM (
            SELECT LOWER(username) AS uname, COUNT(*) AS c
            FROM operators
            GROUP BY LOWER(username)
            HAVING c > 1
        )
        """
    )
    duplicate_usernames = cursor.fetchone()["duplicate_count"] or 0

    if active_count > 0 and admin_count == 0 and log:
        log_operational_warning(
            "No active administrator operator accounts",
            active_operators=active_count,
            hint="Promote or create an administrator to manage operator accounts.",
        )
    if duplicate_usernames and log:
        log_operational_warning(
            "Duplicate operator usernames detected",
            duplicate_groups=duplicate_usernames,
        )

    return {
        "active_operators": active_count,
        "active_administrators": admin_count,
        "duplicate_username_groups": duplicate_usernames,
    }


def _governance_integrity_checks(cursor, *, log: bool) -> dict:
    invalid_roles = fetch_invalid_operator_roles(cursor)
    if invalid_roles and log:
        log_operational_warning(
            "Operators with unrecognized roles detected",
            roles=",".join(invalid_roles),
            valid_roles=",".join(OPERATOR_ROLES),
        )

    role_counts = fetch_operator_role_counts(cursor)
    if (
        role_counts["inactive_count"] >= MAX_INACTIVE_OPERATORS_WARN
        and role_counts["active_count"] > 0
        and log
    ):
        log_operational_warning(
            "High inactive operator account count",
            inactive_operators=role_counts["inactive_count"],
            active_operators=role_counts["active_count"],
        )

    orphaned_workflow = count_orphaned_workflow_history(cursor)
    orphaned_underwriting = count_orphaned_underwriting_decisions(cursor)
    if log:
        warn_orphaned_governance_references(orphaned_workflow + orphaned_underwriting)

    return {
        "invalid_roles": invalid_roles,
        "operator_role_counts": role_counts,
        "orphaned_workflow_events": orphaned_workflow,
        "orphaned_underwriting_records": orphaned_underwriting,
    }


def run_startup_integrity_checks(*, log: bool = True) -> dict:
    """Validate environment and database readiness. Returns a structured status payload."""
    env_issues = validate_environment(strict=False)
    if log:
        for issue in env_issues:
            log_operational_warning("Startup configuration issue", issue=issue)

    directory_issues = _ensure_optional_directories(log=log)
    backup_dir_ok = _validate_backup_path(log=log)

    database_ok = False
    tables_ok = False
    indexes_ok = True
    wal_mode = ""
    operator_count = 0
    missing_indexes: list[str] = []
    operator_sanity: dict = {}
    governance_integrity: dict = {}
    integrity_report: dict = {"overall": "skipped", "counts": {}}
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

        missing_indexes = verify_performance_indexes(cursor)
        indexes_ok = not missing_indexes
        if missing_indexes and log:
            log_operational_warning(
                "Performance indexes missing (will be created on next init_db)",
                indexes=",".join(missing_indexes),
            )

        wal_mode = fetch_sqlite_journal_mode(cursor)
        if wal_mode and wal_mode != "wal" and log:
            log_operational_warning(
                "SQLite journal mode is not WAL",
                journal_mode=wal_mode,
                hint="Restart after init_db or run PRAGMA journal_mode=WAL for better concurrency.",
            )

        operator_count = count_operators(cursor)
        operator_sanity = _operator_sanity_checks(cursor, log=log)
        governance_integrity = _governance_integrity_checks(cursor, log=log)
        integrity_report = run_operational_integrity_checks(cursor, include_environment=False)
        if tables_ok and log:
            from utils.collections_resilience import run_collections_operational_warnings

            run_collections_operational_warnings(cursor)
            from utils.notification_resilience import run_notification_operational_warnings
            from services.notification_alerts import sync_operational_alert_notifications

            run_notification_operational_warnings(cursor)
            try:
                sync_operational_alert_notifications(cursor, actor="system-startup")
                conn.commit()
            except Exception:
                conn.rollback()
        if integrity_report["overall"] == "fail" and log:
            for check in integrity_report["checks"]:
                if check["status"] == "fail":
                    log_operational_warning(
                        "Operational integrity check failed",
                        check=check["name"],
                        detail=check["message"],
                    )
        elif integrity_report["overall"] == "warn" and log:
            for check in integrity_report["checks"]:
                if check["status"] == "warn":
                    log_operational_warning(
                        "Operational integrity warning",
                        check=check["name"],
                        detail=check["message"],
                    )
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
        "indexes_ok": indexes_ok,
        "missing_indexes": missing_indexes,
        "expected_index_count": len(PERFORMANCE_INDEX_NAMES),
        "journal_mode": wal_mode,
        "operator_count": operator_count,
        "operator_sanity": operator_sanity,
        "governance_integrity": governance_integrity,
        "integrity_overall": integrity_report.get("overall", "skipped"),
        "integrity_counts": integrity_report.get("counts", {}),
        "backup_dir_ok": backup_dir_ok,
        "directory_issue_count": len(directory_issues),
        "env_issue_count": len(env_issues),
        "env_issues": env_issues,
        "database_error": database_error,
        "database_path": os.path.abspath(DATABASE_PATH),
    }
    status["ready"] = database_ok and tables_ok and not database_error
    if log:
        log_startup(
            "Startup integrity checks completed",
            **{
                k: v
                for k, v in status.items()
                if k not in {"env_issues", "operator_sanity", "missing_indexes", "governance_integrity"}
            },
        )
    return status


def ensure_production_ready() -> None:
    """Fail fast when production configuration is unsafe."""
    validate_environment(strict=True)
