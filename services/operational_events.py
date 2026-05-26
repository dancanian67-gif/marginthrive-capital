"""Operational event emission (Phase G1) — append-only events with operator notifications."""

from __future__ import annotations

from constants.events import EVENT_CATEGORIES, EVENT_SEVERITIES
from repositories.database import get_db_connection
from repositories.notifications import (
    insert_operational_event,
    insert_operator_notification,
    resolve_operator_id_by_username,
)
from utils.db_write import commit_connection


def session_operator_id() -> int | None:
    try:
        from flask import g

        operator = getattr(g, "operator", None)
        if operator:
            return operator.get("id")
    except RuntimeError:
        return None
    return None


def emit_operational_event(
    *,
    event_category: str,
    severity: str,
    title: str,
    message: str = "",
    application_id: int | None = None,
    actor: str,
    operator_id: int | None = None,
    governance_tag: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    target_operator_id: int | None = None,
    target_username: str | None = None,
    cursor=None,
) -> int | None:
    """
    Record an append-only operational event and a matching operator notification.
    Returns event_id, or None when category/severity is invalid.
    """
    if event_category not in EVENT_CATEGORIES:
        return None
    if severity not in EVENT_SEVERITIES:
        severity = "info"

    resolved_target = target_operator_id
    if resolved_target is None and target_username:
        own_conn = cursor is None
        if own_conn:
            conn = get_db_connection()
            cursor = conn.cursor()
        resolved_target = resolve_operator_id_by_username(cursor, target_username)
        if own_conn:
            conn.close()

    own_connection = cursor is None
    if own_connection:
        conn = get_db_connection()
        cursor = conn.cursor()

    try:
        event_id = insert_operational_event(
            cursor,
            event_category=event_category,
            severity=severity,
            title=title,
            message=message,
            application_id=application_id,
            actor=actor,
            operator_id=operator_id,
            governance_tag=governance_tag,
            source_type=source_type,
            source_id=source_id,
        )
        insert_operator_notification(
            cursor,
            event_id=event_id,
            target_operator_id=resolved_target,
            event_category=event_category,
            severity=severity,
            title=title,
            message=message,
            application_id=application_id,
            governance_tag=governance_tag,
        )
        if own_connection:
            commit_connection(conn, operation_name="operational_event_commit")
    except Exception:
        if own_connection:
            conn.rollback()
        raise
    finally:
        if own_connection:
            conn.close()

    return event_id


def emit_workflow_transition_event(
    *,
    application_id: int,
    actor: str,
    operator_id: int | None,
    status: str,
    risk_level: str,
    is_critical: bool,
    batch_id: str,
) -> None:
    severity = "critical" if is_critical else "info"
    if risk_level in ("High", "Critical"):
        severity = "warning" if severity == "info" else severity
    emit_operational_event(
        event_category="workflow_transition",
        severity=severity,
        title=f"Workflow updated — {status}",
        message=f"Application #{application_id} status is now {status} (risk: {risk_level}).",
        application_id=application_id,
        actor=actor,
        operator_id=operator_id,
        source_type="workflow_history",
        source_id=batch_id,
        target_operator_id=operator_id,
    )


def emit_underwriting_decision_event(
    *,
    application_id: int,
    actor: str,
    operator_id: int | None,
    underwriting_status: str,
    governance_tag: str | None,
    batch_id: str,
) -> None:
    from constants.underwriting import UNDERWRITING_CRITICAL_STATUSES

    critical = underwriting_status in UNDERWRITING_CRITICAL_STATUSES
    emit_operational_event(
        event_category="underwriting_decision",
        severity="critical" if critical else "warning" if underwriting_status == "escalated_review" else "info",
        title=f"Underwriting decision — {underwriting_status}",
        message=f"Application #{application_id} underwriting status recorded as {underwriting_status}.",
        application_id=application_id,
        actor=actor,
        operator_id=operator_id,
        governance_tag=governance_tag,
        source_type="underwriting_decisions",
        source_id=batch_id,
    )


def emit_repayment_recorded_event(
    *,
    application_id: int,
    actor: str,
    operator_id: int | None,
    payment_amount: float,
    batch_id: str,
) -> None:
    emit_operational_event(
        event_category="repayment_recorded",
        severity="info",
        title=f"Repayment recorded — ${payment_amount:,.2f}",
        message=f"Application #{application_id} repayment posted.",
        application_id=application_id,
        actor=actor,
        operator_id=operator_id,
        source_type="repayments",
        source_id=batch_id,
    )


def emit_collections_escalation_event(
    *,
    application_id: int,
    actor: str,
    collections_status: str,
    governance_tag: str | None,
    assigned_to: str | None,
) -> None:
    from constants.collections import COLLECTIONS_CRITICAL_STATUSES

    critical = collections_status in COLLECTIONS_CRITICAL_STATUSES
    emit_operational_event(
        event_category="collections_escalation",
        severity="critical" if critical else "warning",
        title=f"Collections escalation — {collections_status}",
        message=f"Application #{application_id} collections status is {collections_status}.",
        application_id=application_id,
        actor=actor,
        governance_tag=governance_tag,
        target_username=assigned_to,
    )


def emit_broken_promise_event(
    *,
    application_id: int,
    actor: str,
    promise_id: int,
    governance_tag: str | None,
    assigned_to: str | None,
) -> None:
    emit_operational_event(
        event_category="broken_promise",
        severity="critical",
        title="Recovery promise broken",
        message=f"Promise #{promise_id} on application #{application_id} was marked broken.",
        application_id=application_id,
        actor=actor,
        governance_tag=governance_tag,
        source_type="recovery_promises",
        source_id=str(promise_id),
        target_username=assigned_to,
    )


def emit_governance_alert_event(
    *,
    title: str,
    message: str,
    actor: str,
    operator_id: int | None = None,
    application_id: int | None = None,
    governance_tag: str | None = None,
    severity: str = "critical",
) -> None:
    emit_operational_event(
        event_category="governance_alert",
        severity=severity,
        title=title,
        message=message,
        application_id=application_id,
        actor=actor,
        operator_id=operator_id,
        governance_tag=governance_tag,
    )
