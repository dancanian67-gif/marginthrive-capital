"""Centralized operational diagnostics summaries (Phase E4)."""

from __future__ import annotations

import os

from constants.app import DATABASE_PATH
from constants.ops import DEFAULT_BACKUP_DIR, EXPORT_WARN_ROW_THRESHOLD, PERFORMANCE_INDEX_NAMES
from repositories.database import get_db_connection
from utils.env import deployment_safety_issues, is_development, is_production, validate_environment
from utils.integrity_checks import run_operational_integrity_checks
from utils.ops_logging import log_startup
from utils.startup import run_startup_integrity_checks


def build_operational_diagnostics(*, include_environment: bool = True) -> dict:
    """Assemble startup, integrity, and deployment diagnostics into one report."""
    startup = run_startup_integrity_checks(log=False)
    integrity = {"overall": "skipped", "counts": {}, "checks": []}
    database_error = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        integrity = run_operational_integrity_checks(cursor, include_environment=include_environment)
        conn.close()
    except Exception as exc:
        database_error = str(exc)
        integrity = {
            "overall": "fail",
            "counts": {"fail": 1},
            "checks": [
                {
                    "name": "database_integrity",
                    "status": "fail",
                    "message": str(exc),
                    "details": {},
                }
            ],
        }

    backup_dir = os.path.abspath(os.getenv("BACKUP_DIR", DEFAULT_BACKUP_DIR))
    backup_ready = os.path.isdir(backup_dir) and os.access(backup_dir, os.W_OK)

    sections = {
        "startup": {
            "ready": startup.get("ready", False),
            "database_ok": startup.get("database_ok", False),
            "tables_ok": startup.get("tables_ok", False),
            "indexes_ok": startup.get("indexes_ok", False),
            "journal_mode": startup.get("journal_mode", ""),
            "operator_count": startup.get("operator_count", 0),
            "backup_dir_ok": startup.get("backup_dir_ok", False),
            "env_issue_count": startup.get("env_issue_count", 0),
        },
        "governance": startup.get("governance_integrity", {}),
        "operators": startup.get("operator_sanity", {}),
        "integrity": integrity,
        "export": {
            "warn_row_threshold": EXPORT_WARN_ROW_THRESHOLD,
            "backup_dir": backup_dir,
            "backup_ready": backup_ready,
        },
        "indexes": {
            "expected": len(PERFORMANCE_INDEX_NAMES),
            "missing": startup.get("missing_indexes", []),
        },
        "environment": {
            "app_env": os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")),
            "is_production": is_production(),
            "is_development": is_development(),
            "issues": validate_environment(strict=False),
            "deployment_safety": deployment_safety_issues(),
        },
    }

    overall = "ok"
    if database_error or not startup.get("ready") or integrity.get("overall") == "fail":
        overall = "fail"
    elif integrity.get("overall") == "warn" or startup.get("env_issue_count", 0) > 0:
        overall = "warn"

    return {
        "overall": overall,
        "database_path": os.path.abspath(DATABASE_PATH),
        "database_error": database_error,
        "sections": sections,
    }


def format_diagnostics_report(report: dict) -> str:
    """Human-readable diagnostics summary for CLI and operators."""
    lines = [
        "MarginThrive Capital — operational diagnostics",
        f"Overall: {report['overall'].upper()}",
        f"Database: {report['database_path']}",
        "",
        "Startup",
        f"  Ready: {report['sections']['startup']['ready']}",
        f"  Tables: {report['sections']['startup']['tables_ok']}",
        f"  Indexes: {report['sections']['startup']['indexes_ok']}",
        f"  WAL mode: {report['sections']['startup']['journal_mode'] or '—'}",
        f"  Operators: {report['sections']['startup']['operator_count']}",
        f"  Backup dir: {report['sections']['startup']['backup_dir_ok']}",
        "",
        "Governance integrity",
    ]
    gov = report["sections"]["governance"]
    lines.append(f"  Orphaned workflow events: {gov.get('orphaned_workflow_events', 0)}")
    lines.append(f"  Orphaned underwriting records: {gov.get('orphaned_underwriting_records', 0)}")
    lines.append(f"  Invalid roles: {', '.join(gov.get('invalid_roles', [])) or 'none'}")
    lines.append("")
    lines.append("Integrity checks")
    counts = report["sections"]["integrity"].get("counts", {})
    lines.append(f"  OK: {counts.get('ok', 0)}  WARN: {counts.get('warn', 0)}  FAIL: {counts.get('fail', 0)}")
    for check in report["sections"]["integrity"].get("checks", []):
        if check["status"] != "ok":
            lines.append(f"  [{check['status'].upper()}] {check['name']}: {check['message']}")
    env_issues = report["sections"]["environment"].get("deployment_safety", [])
    if env_issues:
        lines.append("")
        lines.append("Deployment safety")
        for issue in env_issues:
            lines.append(f"  - {issue}")
    if report.get("database_error"):
        lines.append("")
        lines.append(f"Database error: {report['database_error']}")
    return "\n".join(lines)


def log_diagnostics_summary(*, verbose: bool = False) -> dict:
    """Build diagnostics and emit a concise startup log line."""
    report = build_operational_diagnostics()
    log_startup(
        "Operational diagnostics completed",
        overall=report["overall"],
        integrity=report["sections"]["integrity"]["overall"],
        startup_ready=report["sections"]["startup"]["ready"],
    )
    if verbose:
        print(format_diagnostics_report(report))
    return report
