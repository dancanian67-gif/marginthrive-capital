import json
import secrets
import sqlite3

from constants.audit import (
    MAX_AUDIT_CONTEXT_LENGTH,
    PUBLIC_INTAKE_ACTOR,
    QUICK_ACTION_AUDIT_TYPES,
    QUICK_ACTIONS_REQUIRING_AUDIT_NOTE,
    SENSITIVE_AUDIT_STATUSES,
    WORKFLOW_AUDIT_FIELDS,
    WORKFLOW_FIELD_ACTION_TYPES,
)
from constants.workflow import (
    APPLICATION_STATUSES,
    DEFAULT_APPLICATION_STATUS,
    DEFAULT_RISK_LEVEL,
    KPI_APPROVED_STATUSES,
    KPI_OPS_REVIEW_SUB_STATUS,
    KPI_REJECTED_STATUS,
)
from repositories.database import get_db_connection
from repositories.officers import ensure_officer_registered
from services.workflow import is_allowed_status_transition
from utils.ops_logging import log_governance_event, log_workflow_failure

def workflow_snapshot_from_row(row: sqlite3.Row | dict) -> dict:
    return {
        "status": row["status"],
        "sub_status": row["sub_status"],
        "risk_level": row["risk_level"],
        "assigned_officer": row["assigned_officer"] or "",
        "flagged_fraud": int(row["flagged_fraud"] or 0),
        "approval_notes": row["approval_notes"] or "",
    }


def workflow_snapshot_from_workflow(workflow: dict) -> dict:
    return {
        "status": workflow["status"],
        "sub_status": workflow["sub_status"],
        "risk_level": workflow["risk_level"],
        "assigned_officer": workflow["assigned_officer"],
        "flagged_fraud": workflow["flagged_fraud"],
        "approval_notes": workflow["approval_notes"],
    }


def workflow_snapshot_json(snapshot: dict) -> str:
    payload = {
        **snapshot,
        "sub_status": snapshot["sub_status"] or "",
    }
    return json.dumps(payload, sort_keys=True)


def format_audit_field_value(field_name: str, value) -> str:
    if field_name == "flagged_fraud":
        return "Flagged" if int(value or 0) else "Clear"
    if field_name == "sub_status":
        return value or "— None —"
    if field_name == "assigned_officer":
        return value or "Unassigned"
    if field_name == "approval_notes":
        text = (value or "").strip()
        return text if text else "—"
    return str(value or "—")


def diff_workflow_snapshots(before: dict, after: dict) -> list[tuple[str, str, str]]:
    changes: list[tuple[str, str, str]] = []
    for field_name in WORKFLOW_AUDIT_FIELDS:
        old_raw = before[field_name]
        new_raw = after[field_name]
        if field_name == "flagged_fraud":
            old_cmp, new_cmp = int(old_raw or 0), int(new_raw or 0)
        elif field_name == "approval_notes":
            old_cmp = (old_raw or "").strip()
            new_cmp = (new_raw or "").strip()
        else:
            old_cmp = old_raw or ""
            new_cmp = new_raw or ""
            if field_name == "sub_status":
                old_cmp = old_cmp or None
                new_cmp = new_cmp or None
        if old_cmp != new_cmp:
            changes.append(
                (
                    field_name,
                    format_audit_field_value(field_name, old_raw),
                    format_audit_field_value(field_name, new_raw),
                )
            )
    return changes


def workflow_change_is_critical(field_name: str, old_value: str, new_value: str) -> bool:
    if field_name == "flagged_fraud":
        return new_value == "Flagged"
    if field_name == "risk_level" and new_value in {"High", "Critical"}:
        return new_value != old_value
    if field_name == "status" and new_value in SENSITIVE_AUDIT_STATUSES.union({KPI_REJECTED_STATUS}):
        return new_value != old_value
    if field_name == "sub_status" and new_value == KPI_OPS_REVIEW_SUB_STATUS:
        return new_value != old_value
    return False


def is_risky_status_transition_warning(current_status: str, next_status: str) -> str | None:
    if current_status == next_status:
        return None

    if not is_allowed_status_transition(current_status, next_status):
        return (
            f"Unusual transition from “{current_status}” to “{next_status}” "
            "(not in the standard allowed path)."
        )

    if current_status in APPLICATION_STATUSES and next_status in APPLICATION_STATUSES:
        current_index = APPLICATION_STATUSES.index(current_status)
        next_index = APPLICATION_STATUSES.index(next_status)
        if next_index > current_index + 1 and next_status not in {KPI_REJECTED_STATUS, "Loan issued"}:
            return (
                f"Skipped intermediate stages moving from “{current_status}” "
                f"to “{next_status}”."
            )

    if next_status == "Management approval" and current_status not in {
        "Approval",
        "Management approval",
    }:
        return "Escalation to Management approval from an early pipeline stage."

    if next_status == KPI_REJECTED_STATUS and current_status in KPI_APPROVED_STATUSES:
        return "Rejecting an application that was already in a post-approval stage."

    return None


def requires_audit_context(
    before: dict,
    after: dict,
    quick_action: str | None = None,
) -> bool:
    if quick_action in QUICK_ACTIONS_REQUIRING_AUDIT_NOTE:
        return True

    if int(after["flagged_fraud"]) != int(before["flagged_fraud"]):
        return True

    if after["status"] != before["status"]:
        if after["status"] in SENSITIVE_AUDIT_STATUSES:
            return True
        if is_risky_status_transition_warning(before["status"], after["status"]):
            return True

    if after["risk_level"] == "Critical" and after["risk_level"] != before["risk_level"]:
        return True

    return False


def normalize_audit_context(raw_value: str) -> str:
    return (raw_value or "").strip()[:MAX_AUDIT_CONTEXT_LENGTH]


def validate_audit_context(raw_value: str, required: bool) -> tuple[str, str | None]:
    notes = normalize_audit_context(raw_value)
    if required and not notes:
        return "", "An operational note is required for this sensitive workflow action."
    if len((raw_value or "").strip()) > MAX_AUDIT_CONTEXT_LENGTH:
        return "", f"Operational note must be {MAX_AUDIT_CONTEXT_LENGTH} characters or fewer."
    return notes, None


def history_event_summary(field_name: str, old_value: str, new_value: str) -> str:
    labels = {
        "status": "Status",
        "sub_status": "Sub-status",
        "risk_level": "Risk level",
        "flagged_fraud": "Fraud flag",
        "assigned_officer": "Assigned officer",
        "approval_notes": "Approval notes",
    }
    label = labels.get(field_name, field_name.replace("_", " ").title())
    if field_name == "approval_notes":
        return f"{label} updated"
    return f"{label}: {old_value} → {new_value}"


def insert_workflow_history_entries(
    cursor,
    *,
    application_id: int,
    batch_id: str,
    actor: str,
    before: dict,
    after: dict,
    changes: list[tuple[str, str, str]],
    action_type: str,
    context_notes: str,
    transition_warning: str | None,
) -> None:
    if not changes:
        return

    previous_state = workflow_snapshot_json(before)
    new_state = workflow_snapshot_json(after)

    for field_name, old_value, new_value in changes:
        field_action = WORKFLOW_FIELD_ACTION_TYPES.get(field_name, action_type)
        is_critical = 1 if workflow_change_is_critical(field_name, old_value, new_value) else 0
        cursor.execute(
            """
            INSERT INTO workflow_history (
                application_id,
                batch_id,
                action_type,
                field_name,
                old_value,
                new_value,
                previous_state,
                new_state,
                actor,
                context_notes,
                is_critical,
                transition_warning,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                application_id,
                batch_id,
                field_action,
                field_name,
                old_value,
                new_value,
                previous_state,
                new_state,
                actor,
                context_notes,
                is_critical,
                transition_warning,
            ),
        )


def persist_workflow_update(
    application_id: int,
    application: sqlite3.Row,
    workflow: dict,
    actor: str,
    *,
    quick_action: str | None = None,
    context_notes: str = "",
    transition_warning: str | None = None,
) -> None:
    before = workflow_snapshot_from_row(application)
    after = workflow_snapshot_from_workflow(workflow)
    changes = diff_workflow_snapshots(before, after)
    if not changes:
        return

    batch_id = secrets.token_hex(8)
    action_type = QUICK_ACTION_AUDIT_TYPES.get(quick_action or "", "workflow_update")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if workflow["assigned_officer"]:
            ensure_officer_registered(cursor, workflow["assigned_officer"])

        cursor.execute(
            """
            UPDATE applications
            SET
                status = ?,
                sub_status = ?,
                risk_level = ?,
                assigned_officer = ?,
                approval_notes = ?,
                flagged_fraud = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                workflow["status"],
                workflow["sub_status"],
                workflow["risk_level"],
                workflow["assigned_officer"],
                workflow["approval_notes"],
                workflow["flagged_fraud"],
                application_id,
            ),
        )

        insert_workflow_history_entries(
            cursor,
            application_id=application_id,
            batch_id=batch_id,
            actor=actor,
            before=before,
            after=after,
            changes=changes,
            action_type=action_type,
            context_notes=context_notes,
            transition_warning=transition_warning,
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        log_workflow_failure(
            "Workflow persistence failed in audit service",
            application_id=application_id,
            actor=actor,
            quick_action=quick_action,
            error=str(exc),
        )
        raise
    finally:
        conn.close()

    if any(workflow_change_is_critical(field, old, new) for field, old, new in changes):
        log_governance_event(
            "Critical workflow change recorded",
            critical=True,
            application_id=application_id,
            actor=actor,
            batch_id=batch_id,
        )


def group_workflow_history_batches(rows: list) -> list[dict]:
    batches: list[dict] = []
    index_by_batch: dict[str, int] = {}

    for row in rows:
        batch_id = row["batch_id"]
        event = {
            "field_name": row["field_name"],
            "summary": history_event_summary(row["field_name"], row["old_value"], row["new_value"]),
            "old_value": row["old_value"],
            "new_value": row["new_value"],
            "is_critical": bool(row["is_critical"]),
        }
        if batch_id in index_by_batch:
            batch = batches[index_by_batch[batch_id]]
            batch["events"].append(event)
            batch["is_critical"] = batch["is_critical"] or event["is_critical"]
        else:
            index_by_batch[batch_id] = len(batches)
            batches.append(
                {
                    "batch_id": batch_id,
                    "action_type": row["action_type"],
                    "actor": row["actor"],
                    "created_at": row["created_at"],
                    "context_notes": row["context_notes"] or "",
                    "transition_warning": row["transition_warning"] or "",
                    "is_critical": bool(row["is_critical"]),
                    "events": [event],
                }
            )

    return batches


def log_application_created(cursor, application_id: int) -> None:
    after = {
        "status": DEFAULT_APPLICATION_STATUS,
        "sub_status": None,
        "risk_level": DEFAULT_RISK_LEVEL,
        "assigned_officer": "",
        "flagged_fraud": 0,
        "approval_notes": "",
    }
    before = {
        "status": "",
        "sub_status": None,
        "risk_level": "",
        "assigned_officer": "",
        "flagged_fraud": 0,
        "approval_notes": "",
    }
    batch_id = secrets.token_hex(8)
    insert_workflow_history_entries(
        cursor,
        application_id=application_id,
        batch_id=batch_id,
        actor=PUBLIC_INTAKE_ACTOR,
        before=before,
        after=after,
        changes=[("status", "—", DEFAULT_APPLICATION_STATUS)],
        action_type="application_created",
        context_notes="Application submitted via public intake form.",
        transition_warning=None,
    )

