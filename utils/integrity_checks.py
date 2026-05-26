"""Reusable operational integrity checks (Phase E4). Non-destructive diagnostics only."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from constants.governance import EXPORT_TYPE_METADATA
from constants.ops import EXPORT_WARN_ROW_THRESHOLD, PERFORMANCE_INDEX_NAMES, REQUIRED_DATABASE_TABLES
from constants.operators import OPERATOR_ROLES
from constants.reporting import REPORT_EXPORT_MAX_ROWS, REPORT_EXPORT_TYPES
from constants.workflow import APPLICATION_STATUSES
from repositories.database import fetch_sqlite_journal_mode
from repositories.governance_validation import (
    count_orphaned_underwriting_decisions,
    count_orphaned_workflow_history,
    fetch_invalid_operator_roles,
    fetch_operator_role_counts,
)
from repositories.indexes import verify_performance_indexes
from repositories.operators import count_active_administrators
from utils.env import deployment_safety_issues, validate_environment

CheckStatus = Literal["ok", "warn", "fail"]


@dataclass
class IntegrityCheckResult:
    name: str
    status: CheckStatus
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _ok(name: str, message: str, **details) -> IntegrityCheckResult:
    return IntegrityCheckResult(name, "ok", message, details)


def _warn(name: str, message: str, **details) -> IntegrityCheckResult:
    return IntegrityCheckResult(name, "warn", message, details)


def _fail(name: str, message: str, **details) -> IntegrityCheckResult:
    return IntegrityCheckResult(name, "fail", message, details)


def check_required_tables(cursor, existing_tables: set[str] | None = None) -> IntegrityCheckResult:
    if existing_tables is None:
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
    missing = [t for t in REQUIRED_DATABASE_TABLES if t not in existing_tables]
    if missing:
        return _fail("required_tables", f"Missing tables: {', '.join(missing)}", missing=missing)
    return _ok("required_tables", "All required tables present")


def check_performance_indexes(cursor) -> IntegrityCheckResult:
    missing = verify_performance_indexes(cursor)
    if missing:
        return _warn(
            "performance_indexes",
            f"Missing {len(missing)} performance index(es)",
            missing=missing,
            expected=len(PERFORMANCE_INDEX_NAMES),
        )
    return _ok("performance_indexes", f"All {len(PERFORMANCE_INDEX_NAMES)} indexes present")


def check_sqlite_wal_mode(cursor) -> IntegrityCheckResult:
    mode = fetch_sqlite_journal_mode(cursor)
    if mode != "wal":
        return _warn(
            "sqlite_wal",
            f"Journal mode is '{mode or 'unknown'}' (WAL recommended)",
            journal_mode=mode,
        )
    return _ok("sqlite_wal", "SQLite WAL journal mode active")


def check_operator_roles(cursor) -> IntegrityCheckResult:
    invalid = fetch_invalid_operator_roles(cursor)
    if invalid:
        return _fail(
            "operator_roles",
            "Operators with invalid roles detected",
            invalid_roles=invalid,
            valid_roles=list(OPERATOR_ROLES),
        )
    return _ok("operator_roles", "All operator roles are valid")


def check_active_administrator(cursor) -> IntegrityCheckResult:
    active = count_active_administrators(cursor)
    cursor.execute("SELECT COUNT(*) FROM operators WHERE active = 1")
    active_total = cursor.fetchone()[0] or 0
    if active_total > 0 and active == 0:
        return _warn(
            "active_administrator",
            "No active administrator accounts",
            active_operators=active_total,
        )
    return _ok("active_administrator", f"{active} active administrator(s)")


def check_orphaned_audit_references(cursor) -> IntegrityCheckResult:
    workflow_orphans = count_orphaned_workflow_history(cursor)
    underwriting_orphans = count_orphaned_underwriting_decisions(cursor)
    total = workflow_orphans + underwriting_orphans
    if total:
        return _warn(
            "orphaned_audit_references",
            f"{total} orphaned governance record(s)",
            workflow_history=workflow_orphans,
            underwriting_decisions=underwriting_orphans,
        )
    return _ok("orphaned_audit_references", "No orphaned workflow or underwriting references")


def check_orphaned_repayments(cursor) -> IntegrityCheckResult:
    cursor.execute(
        """
        SELECT COUNT(*) FROM repayments r
        WHERE NOT EXISTS (SELECT 1 FROM applications a WHERE a.id = r.application_id)
        """
    )
    count = cursor.fetchone()[0] or 0
    if count:
        return _warn("orphaned_repayments", f"{count} repayment(s) without application", count=count)
    return _ok("orphaned_repayments", "All repayments reference valid applications")


def check_malformed_workflow_states(cursor) -> IntegrityCheckResult:
    placeholders = ", ".join("?" * len(APPLICATION_STATUSES))
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM applications
        WHERE status IS NULL OR status = '' OR status NOT IN ({placeholders})
        """,
        APPLICATION_STATUSES,
    )
    count = cursor.fetchone()[0] or 0
    if count:
        return _warn(
            "malformed_workflow_states",
            f"{count} application(s) with invalid status",
            count=count,
        )
    return _ok("malformed_workflow_states", "Application workflow statuses are valid")


def check_underwriting_consistency(cursor) -> IntegrityCheckResult:
    cursor.execute(
        """
        SELECT COUNT(*) FROM applications
        WHERE underwriting_status IS NULL OR TRIM(underwriting_status) = ''
        """
    )
    empty_status = cursor.fetchone()[0] or 0
    cursor.execute(
        """
        SELECT COUNT(*) FROM underwriting_decisions ud
        WHERE ud.batch_id IS NULL OR TRIM(ud.batch_id) = ''
           OR ud.actor IS NULL OR TRIM(ud.actor) = ''
        """
    )
    bad_decisions = cursor.fetchone()[0] or 0
    issues = empty_status + bad_decisions
    if issues:
        return _warn(
            "underwriting_consistency",
            "Underwriting data consistency issues detected",
            empty_application_status=empty_status,
            invalid_decision_rows=bad_decisions,
        )
    return _ok("underwriting_consistency", "Underwriting fields and decision rows look consistent")


def check_governance_actor_attribution(cursor) -> IntegrityCheckResult:
    cursor.execute(
        """
        SELECT COUNT(*) FROM workflow_history
        WHERE actor IS NULL OR TRIM(actor) = ''
        """
    )
    workflow_missing = cursor.fetchone()[0] or 0
    cursor.execute(
        """
        SELECT COUNT(*) FROM underwriting_decisions
        WHERE actor IS NULL OR TRIM(actor) = '' OR reviewed_by IS NULL OR TRIM(reviewed_by) = ''
        """
    )
    underwriting_missing = cursor.fetchone()[0] or 0
    cursor.execute(
        """
        SELECT COUNT(*) FROM repayments
        WHERE actor IS NULL OR TRIM(actor) = ''
        """
    )
    repayment_missing = cursor.fetchone()[0] or 0
    total = workflow_missing + underwriting_missing + repayment_missing
    if total:
        return _warn(
            "governance_actor_attribution",
            f"{total} governance row(s) missing actor attribution",
            workflow_history=workflow_missing,
            underwriting_decisions=underwriting_missing,
            repayments=repayment_missing,
        )
    return _ok("governance_actor_attribution", "Actor attribution populated on governance rows")


def check_workflow_history_append_only(cursor) -> IntegrityCheckResult:
    cursor.execute(
        """
        SELECT COUNT(*) FROM sqlite_master
        WHERE type = 'trigger' AND tbl_name = 'workflow_history'
        """
    )
    triggers = cursor.fetchone()[0] or 0
    if triggers:
        return _warn(
            "workflow_history_append_only",
            f"{triggers} trigger(s) on workflow_history (review for mutability)",
            trigger_count=triggers,
        )
    return _ok("workflow_history_append_only", "No triggers mutating workflow_history")


def check_repayment_history_continuity(cursor) -> IntegrityCheckResult:
    cursor.execute(
        """
        SELECT COUNT(*) FROM repayments
        WHERE balance_after > balance_before + 0.001
           OR balance_before < 0 OR balance_after < 0
        """
    )
    invalid = cursor.fetchone()[0] or 0
    if invalid:
        return _warn(
            "repayment_history_continuity",
            f"{invalid} repayment(s) with inconsistent balances",
            invalid_rows=invalid,
        )
    return _ok("repayment_history_continuity", "Repayment balance continuity checks passed")


def check_collections_reference_consistency(cursor) -> IntegrityCheckResult:
    from repositories.collections import count_orphaned_collections_history, fetch_invalid_collections_statuses

    issues: list[str] = []
    orphans = count_orphaned_collections_history(cursor)
    if orphans:
        issues.append(f"{orphans} orphaned collections_history row(s)")

    invalid_statuses = fetch_invalid_collections_statuses(cursor)
    if invalid_statuses:
        issues.append(f"invalid collections_status values: {invalid_statuses}")

    cursor.execute(
        """
        SELECT COUNT(*) FROM applications
        WHERE collections_next_follow_up IS NOT NULL
          AND TRIM(collections_next_follow_up) != ''
          AND collections_next_follow_up NOT GLOB '????-??-??'
        """
    )
    bad_dates = cursor.fetchone()[0] or 0
    if bad_dates:
        issues.append(f"{bad_dates} malformed collections_next_follow_up date(s)")

    if issues:
        return _warn(
            "collections_reference_consistency",
            "; ".join(issues),
            orphans=orphans,
            invalid_statuses=invalid_statuses,
            bad_follow_up_dates=bad_dates,
        )
    return _ok(
        "collections_reference_consistency",
        "Collections references and delinquency fields are consistent",
    )


def check_collections_intelligence_consistency(cursor) -> IntegrityCheckResult:
    from constants.collections import COLLECTIONS_PRIORITIES
    from repositories.collections_intelligence import (
        count_stale_critical_risk_accounts,
        count_unresolved_legal_escalations,
    )
    from repositories.collections import count_orphaned_collections_history

    issues: list[str] = []
    orphans = count_orphaned_collections_history(cursor)
    if orphans:
        issues.append(f"{orphans} orphaned collections_history row(s)")

    placeholders = ", ".join("?" * len(COLLECTIONS_PRIORITIES))
    cursor.execute(
        f"""
        SELECT DISTINCT collections_priority FROM applications
        WHERE collections_priority IS NOT NULL AND collections_priority != ''
          AND collections_priority NOT IN ({placeholders})
        LIMIT 5
        """,
        tuple(COLLECTIONS_PRIORITIES),
    )
    bad_priority = [row[0] for row in cursor.fetchall()]
    if bad_priority:
        issues.append(f"invalid collections_priority: {bad_priority}")

    stale_critical = count_stale_critical_risk_accounts(cursor, 14)
    if stale_critical:
        issues.append(f"{stale_critical} stale critical-risk account(s) without recent contact")

    unresolved_legal = count_unresolved_legal_escalations(cursor)
    if unresolved_legal:
        issues.append(f"{unresolved_legal} unresolved legal escalation(s) in active queue")

    cursor.execute(
        """
        SELECT COUNT(*) FROM applications
        WHERE loan_lifecycle_status IN ('overdue', 'defaulted', 'active', 'repaying')
          AND due_date IS NOT NULL AND TRIM(due_date) != ''
          AND COALESCE(outstanding_balance, 0) > 0
          AND date(due_date) < date('now')
          AND collections_status = 'not_in_collections'
        """
    )
    delinq_not_queued = cursor.fetchone()[0] or 0
    if delinq_not_queued:
        issues.append(
            f"{delinq_not_queued} past-due account(s) not marked for collections (informational)"
        )

    if issues:
        return _warn("collections_intelligence_consistency", "; ".join(issues))
    return _ok(
        "collections_intelligence_consistency",
        "Collections intelligence and delinquency signals are consistent",
    )


def check_promise_reference_consistency(cursor) -> IntegrityCheckResult:
    from repositories.promises import (
        count_orphaned_promises_application,
        count_orphaned_promise_history,
        fetch_impossible_fulfillment_rows,
        fetch_invalid_promise_statuses,
        fetch_unresolved_expired_active,
    )

    issues: list[str] = []
    orphans_h = count_orphaned_promise_history(cursor)
    if orphans_h:
        issues.append(f"{orphans_h} orphaned recovery_promise_history row(s)")
    orphans_p = count_orphaned_promises_application(cursor)
    if orphans_p:
        issues.append(f"{orphans_p} orphaned recovery_promises row(s)")
    invalid = fetch_invalid_promise_statuses(cursor)
    if invalid:
        issues.append(f"invalid promise_status: {invalid}")
    impossible = fetch_impossible_fulfillment_rows(cursor)
    if impossible:
        issues.append(f"{impossible} fulfilled promise(s) without fulfilled_at timestamp")
    stale = fetch_unresolved_expired_active(cursor)
    if stale:
        issues.append(f"{stale} long-overdue active promise(s) (review recommended)")

    cursor.execute(
        """
        SELECT COUNT(*) FROM recovery_promises rp
        WHERE promise_status = 'fulfilled'
          AND NOT EXISTS (
              SELECT 1 FROM applications a WHERE a.id = rp.application_id
          )
        """
    )
    if issues:
        return _warn("promise_reference_consistency", "; ".join(issues))
    return _ok(
        "promise_reference_consistency",
        "Recovery promise references and states are consistent",
    )


def check_notification_reference_consistency(cursor) -> IntegrityCheckResult:
    from repositories.notifications import (
        count_excessive_notification_backlog,
        count_invalid_acknowledgement_states,
        count_orphaned_notifications,
        count_unresolved_critical_notifications,
    )

    issues: list[str] = []
    orphans = count_orphaned_notifications(cursor)
    if orphans:
        issues.append(f"{orphans} orphaned operator notification(s)")
    invalid_ack = count_invalid_acknowledgement_states(cursor)
    if invalid_ack:
        issues.append(f"{invalid_ack} notification(s) with invalid acknowledgement state")
    critical = count_unresolved_critical_notifications(cursor)
    if critical >= 50:
        issues.append(f"{critical} unresolved critical notifications (review backlog)")
    backlog = count_excessive_notification_backlog(cursor, threshold=500)
    if backlog:
        issues.append(f"{backlog} unacknowledged notifications (accumulation warning)")

    if issues:
        return _warn("notification_reference_consistency", "; ".join(issues))
    return _ok(
        "notification_reference_consistency",
        "Operational events and notifications are consistent",
    )


def check_export_governance_config() -> IntegrityCheckResult:
    missing_report_types = sorted(
        t
        for t in REPORT_EXPORT_TYPES
        if t not in EXPORT_TYPE_METADATA and f"report_{t}" not in EXPORT_TYPE_METADATA
    )
    issues = []
    if missing_report_types:
        issues.append(f"missing metadata: {missing_report_types}")
    if EXPORT_WARN_ROW_THRESHOLD > REPORT_EXPORT_MAX_ROWS:
        issues.append("export warn threshold exceeds max rows cap")
    if issues:
        return _warn(
            "export_governance_config",
            "; ".join(issues),
            missing_report_types=missing_report_types,
            warn_threshold=EXPORT_WARN_ROW_THRESHOLD,
            max_rows=REPORT_EXPORT_MAX_ROWS,
        )
    return _ok("export_governance_config", "Export types and thresholds configured consistently")


def check_environment_profile() -> list[IntegrityCheckResult]:
    results: list[IntegrityCheckResult] = []
    for issue in validate_environment(strict=False):
        results.append(_warn("environment", issue))
    for issue in deployment_safety_issues():
        results.append(_warn("deployment_safety", issue))
    if not results:
        results.append(_ok("environment", "Environment profile checks passed"))
    return results


def run_operational_integrity_checks(cursor, *, include_environment: bool = True) -> dict:
    """Run all database and configuration integrity checks."""
    checks: list[IntegrityCheckResult] = [
        check_required_tables(cursor),
        check_performance_indexes(cursor),
        check_sqlite_wal_mode(cursor),
        check_operator_roles(cursor),
        check_active_administrator(cursor),
        check_orphaned_audit_references(cursor),
        check_orphaned_repayments(cursor),
        check_malformed_workflow_states(cursor),
        check_underwriting_consistency(cursor),
        check_governance_actor_attribution(cursor),
        check_workflow_history_append_only(cursor),
        check_repayment_history_continuity(cursor),
        check_export_governance_config(),
        check_collections_reference_consistency(cursor),
        check_collections_intelligence_consistency(cursor),
        check_promise_reference_consistency(cursor),
        check_notification_reference_consistency(cursor),
    ]
    if include_environment:
        checks.extend(check_environment_profile())

    counts = {"ok": 0, "warn": 0, "fail": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1

    overall: CheckStatus = "ok"
    if counts["fail"]:
        overall = "fail"
    elif counts["warn"]:
        overall = "warn"

    return {
        "overall": overall,
        "counts": counts,
        "checks": [c.to_dict() for c in checks],
    }
