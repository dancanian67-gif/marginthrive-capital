"""Governance escalation logging and audit context tagging (Phase E3)."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from constants.governance import (
    GOVERNANCE_DENIED_REPEAT_THRESHOLD,
    GOVERNANCE_DENIED_WINDOW_SECONDS,
    GOV_TAG_FRAUD_OVERRIDE,
    GOV_TAG_HIGH_RISK_OVERRIDE,
    GOV_TAG_LOAN_CLOSURE,
    GOV_TAG_LOAN_DISTRESS,
    GOV_TAG_OPERATOR_DEACTIVATED,
    GOV_TAG_REPAYMENT_RECORD,
    GOV_TAG_SENSITIVE_EXPORT,
    GOV_TAG_UNDERWRITING_ESCALATION,
    GOV_TAG_UNDERWRITING_REJECTION,
    GOV_TAG_COLLECTIONS_ESCALATION,
    GOV_TAG_COLLECTIONS_LEGAL,
    GOV_TAG_COLLECTIONS_WRITEOFF,
    GOV_TAG_COLLECTIONS_CLOSURE,
    GOV_TAG_COLLECTIONS_DISPUTE,
    GOV_TAG_COLLECTIONS_FRAUD_RECOVERY,
    GOV_TAG_PROMISE_CREATED,
    GOV_TAG_PROMISE_BROKEN,
    GOV_TAG_PROMISE_FULFILLED,
    GOV_TAG_PROMISE_CANCELLED,
)
from constants.collections import COLLECTIONS_CRITICAL_STATUSES, COLLECTIONS_SENSITIVE_STATUSES
from constants.underwriting import UNDERWRITING_CRITICAL_STATUSES
from utils.auth import operator_audit_label
from utils.ops_logging import log_governance_event, log_operational_warning

_denial_tracker: dict[str, list[float]] = defaultdict(list)


def format_governance_tag(tag: str) -> str:
    if tag.startswith("["):
        return tag
    return f"[{tag}]"


def append_governance_context(notes: str, tag: str) -> str:
    """Prefix audit context_notes with a governance tag when not already present."""
    marker = tag if tag.startswith("[") else format_governance_tag(tag)
    existing = (notes or "").strip()
    if marker in existing:
        return existing
    if existing:
        return f"{marker} {existing}"
    return marker


def _prune_denial_window(timestamps: list[float], now: float) -> list[float]:
    cutoff = now - GOVERNANCE_DENIED_WINDOW_SECONDS
    return [value for value in timestamps if value >= cutoff]


def log_permission_denied(
    permission: str,
    *,
    operator: dict | None,
    path: str,
    method: str,
    action: str,
) -> None:
    actor = operator_audit_label(operator) if operator else "unknown-operator"
    role = (operator or {}).get("role", "unknown")
    operator_id = (operator or {}).get("id")
    key = f"{operator_id}:{permission}:{action}"
    now = time.time()
    window = _prune_denial_window(_denial_tracker[key], now)
    window.append(now)
    _denial_tracker[key] = window

    log_governance_event(
        "Unauthorized operational action denied",
        critical=False,
        event_subtype="permission.denied",
        actor=actor,
        role=role,
        permission=permission,
        action=action,
        path=path,
        method=method,
        attempt_count=len(window),
    )

    if len(window) >= GOVERNANCE_DENIED_REPEAT_THRESHOLD:
        log_governance_event(
            "Repeated unauthorized action attempts",
            critical=True,
            event_subtype="permission.denied.repeated",
            actor=actor,
            role=role,
            permission=permission,
            action=action,
            attempt_count=len(window),
            window_seconds=GOVERNANCE_DENIED_WINDOW_SECONDS,
        )
        from constants.governance import GOV_TAG_NOTIFICATION_PERMISSION_DENIED
        from services.operational_events import emit_governance_alert_event

        emit_governance_alert_event(
            title="Repeated permission denials",
            message=(
                f"Operator {actor} attempted {action} ({permission}) "
                f"{len(window)} times within {GOVERNANCE_DENIED_WINDOW_SECONDS}s."
            ),
            actor=actor,
            operator_id=operator_id,
            governance_tag=GOV_TAG_NOTIFICATION_PERMISSION_DENIED,
            severity="critical",
        )


def log_admin_only_operation(*, action: str, actor: str, **fields: Any) -> None:
    log_governance_event(
        "Administrator-only operation",
        critical=False,
        event_subtype="admin.operation",
        action=action,
        actor=actor,
        **fields,
    )


def log_sensitive_export(
    *,
    export_type: str,
    actor: str,
    role: str,
    sensitivity: str,
    row_count: int | None = None,
    **fields: Any,
) -> None:
    critical = sensitivity == "governance" or (row_count or 0) >= 5000
    log_governance_event(
        "Governance-classified export generated",
        critical=critical,
        event_subtype="export.sensitive",
        export_type=export_type,
        actor=actor,
        role=role,
        sensitivity=sensitivity,
        row_count=row_count,
        governance_tag=GOV_TAG_SENSITIVE_EXPORT,
        **fields,
    )


def log_high_risk_workflow_override(
    *,
    application_id: int,
    actor: str,
    transition_warning: str | None,
    **fields: Any,
) -> None:
    if not transition_warning:
        return
    log_governance_event(
        "High-risk workflow transition recorded",
        critical=True,
        event_subtype="workflow.high_risk_override",
        application_id=application_id,
        actor=actor,
        governance_tag=GOV_TAG_HIGH_RISK_OVERRIDE,
        transition_warning=transition_warning,
        **fields,
    )


def log_underwriting_governance(
    *,
    application_id: int,
    actor: str,
    underwriting_status: str,
    previous_status: str | None = None,
) -> None:
    if underwriting_status in UNDERWRITING_CRITICAL_STATUSES:
        if underwriting_status == "rejected":
            tag = GOV_TAG_UNDERWRITING_REJECTION
            message = "Underwriting rejection recorded"
        elif underwriting_status == "escalated_review":
            tag = GOV_TAG_UNDERWRITING_ESCALATION
            message = "Underwriting escalation recorded"
        else:
            tag = GOV_TAG_UNDERWRITING_ESCALATION
            message = "Critical underwriting status recorded"
        log_governance_event(
            message,
            critical=True,
            event_subtype="underwriting.critical",
            application_id=application_id,
            actor=actor,
            governance_tag=tag,
            underwriting_status=underwriting_status,
            previous_status=previous_status or "",
        )
    elif previous_status in ("approved", "conditionally_approved") and underwriting_status == "rejected":
        log_governance_event(
            "Underwriting rejection override from approved state",
            critical=True,
            event_subtype="underwriting.rejection_override",
            application_id=application_id,
            actor=actor,
            governance_tag=GOV_TAG_UNDERWRITING_REJECTION,
            previous_status=previous_status,
            underwriting_status=underwriting_status,
        )


def governance_context_for_fraud_clear() -> str:
    return format_governance_tag(GOV_TAG_FRAUD_OVERRIDE)


def governance_context_for_repayment() -> str:
    return format_governance_tag(GOV_TAG_REPAYMENT_RECORD)


def governance_context_for_loan_lifecycle(new_status: str) -> str | None:
    if new_status in ("completed", "written_off"):
        return format_governance_tag(GOV_TAG_LOAN_CLOSURE)
    if new_status in ("defaulted", "overdue"):
        return format_governance_tag(GOV_TAG_LOAN_DISTRESS)
    return None


def governance_context_for_operator_deactivation() -> str:
    return format_governance_tag(GOV_TAG_OPERATOR_DEACTIVATED)


def governance_context_for_collections_status(
    new_status: str,
    *,
    flagged_fraud: bool = False,
) -> str | None:
    tags: list[str] = []
    if new_status == "legal_escalation":
        tags.append(format_governance_tag(GOV_TAG_COLLECTIONS_LEGAL))
    elif new_status == "write_off_recommended":
        tags.append(format_governance_tag(GOV_TAG_COLLECTIONS_WRITEOFF))
    elif new_status == "resolved":
        tags.append(format_governance_tag(GOV_TAG_COLLECTIONS_CLOSURE))
    elif new_status in COLLECTIONS_SENSITIVE_STATUSES:
        tags.append(format_governance_tag(GOV_TAG_COLLECTIONS_ESCALATION))
    if flagged_fraud and new_status in COLLECTIONS_SENSITIVE_STATUSES.union({"resolved"}):
        tags.append(format_governance_tag(GOV_TAG_COLLECTIONS_FRAUD_RECOVERY))
    if not tags:
        return None
    return " ".join(tags)


def log_collections_governance(
    *,
    application_id: int,
    actor: str,
    collections_status: str,
    previous_status: str | None = None,
) -> None:
    if collections_status not in COLLECTIONS_CRITICAL_STATUSES and collections_status != "resolved":
        return
    if collections_status == "legal_escalation":
        tag = GOV_TAG_COLLECTIONS_LEGAL
        message = "Collections legal escalation recorded"
    elif collections_status == "write_off_recommended":
        tag = GOV_TAG_COLLECTIONS_WRITEOFF
        message = "Collections write-off recommendation recorded"
    elif collections_status == "resolved":
        tag = GOV_TAG_COLLECTIONS_CLOSURE
        message = "Collections recovery closure recorded"
    else:
        tag = GOV_TAG_COLLECTIONS_ESCALATION
        message = "Collections escalation recorded"
    log_governance_event(
        message,
        critical=True,
        event_subtype="collections.critical",
        application_id=application_id,
        actor=actor,
        governance_tag=tag,
        collections_status=collections_status,
        previous_status=previous_status or "",
    )


def governance_context_for_promise_status(status: str, *, action: str = "updated") -> str | None:
    if action == "created":
        return format_governance_tag(GOV_TAG_PROMISE_CREATED)
    if status == "broken":
        return format_governance_tag(GOV_TAG_PROMISE_BROKEN)
    if status == "fulfilled":
        return format_governance_tag(GOV_TAG_PROMISE_FULFILLED)
    if status in ("cancelled", "expired"):
        return format_governance_tag(GOV_TAG_PROMISE_CANCELLED)
    return None


def log_promise_governance(
    *,
    application_id: int,
    promise_id: int,
    actor: str,
    promise_status: str,
    action: str,
    previous_status: str | None = None,
) -> None:
    if promise_status not in ("broken", "fulfilled") and action != "created":
        return
    if promise_status == "broken":
        tag = GOV_TAG_PROMISE_BROKEN
        message = "Recovery promise broken"
        critical = True
    elif promise_status == "fulfilled":
        tag = GOV_TAG_PROMISE_FULFILLED
        message = "Recovery promise fulfilled"
        critical = False
    else:
        tag = GOV_TAG_PROMISE_CREATED
        message = "Recovery promise created"
        critical = False
    log_governance_event(
        message,
        critical=critical,
        event_subtype="collections.promise",
        application_id=application_id,
        promise_id=promise_id,
        actor=actor,
        governance_tag=tag,
        promise_status=promise_status,
        previous_status=previous_status or "",
    )


def warn_orphaned_governance_references(count: int) -> None:
    if count:
        log_operational_warning(
            "Orphaned workflow audit references detected",
            orphaned_events=count,
            hint="Audit rows reference missing applications; investigate data integrity.",
        )
