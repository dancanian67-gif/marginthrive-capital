"""Recovery promise service layer (Phase F3)."""

from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import date, datetime

from constants.promises import (
    MAX_PROMISE_AMOUNT,
    MAX_PROMISE_NOTES_LENGTH,
    PROMISE_AUDIT_FIELDS,
    PROMISE_CRITICAL_STATUSES,
    PROMISE_FIELD_ACTION_TYPES,
    PROMISE_STATUSES,
    PROMISE_STATUSES_REQUIRING_CONTEXT,
    PROMISE_STATUS_LABELS,
    TERMINAL_PROMISE_STATUSES,
)
from repositories.database import get_db_connection
from repositories.promises import (
    fetch_active_promise,
    fetch_promise_by_id,
    insert_promise_history_record,
)
from utils.db_write import commit_connection
from utils.governance import (
    append_governance_context,
    governance_context_for_promise_status,
    log_promise_governance,
)
from utils.ops_logging import log_governance_event, log_workflow_failure


def promise_snapshot_from_row(row: sqlite3.Row | dict) -> dict:
    return {
        "promise_amount": float(row["promise_amount"]),
        "promise_date": (row["promise_date"] or "").strip(),
        "promise_status": row["promise_status"] or "active",
        "commitment_notes": (row["commitment_notes"] or "").strip(),
    }


def promise_snapshot_from_form(data) -> dict:
    amount_raw = (data.get("promise_amount") or "").strip()
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = -1.0
    return {
        "promise_amount": amount,
        "promise_date": (data.get("promise_date") or "").strip(),
        "promise_status": (data.get("promise_status") or "active").strip(),
        "commitment_notes": (data.get("commitment_notes") or "").strip(),
    }


def _format_promise_field(field_name: str, value) -> str:
    if field_name == "promise_status":
        return PROMISE_STATUS_LABELS.get(str(value or ""), str(value or "—"))
    if field_name in {"promise_amount", "promise_date"}:
        return str(value) if value not in (None, "") else "—"
    text = (value or "").strip() if isinstance(value, str) else value
    return str(text) if text not in (None, "") else "—"


def diff_promise_snapshots(before: dict, after: dict) -> list[tuple[str, str, str]]:
    changes: list[tuple[str, str, str]] = []
    for field_name in PROMISE_AUDIT_FIELDS:
        old_raw = before.get(field_name, "")
        new_raw = after.get(field_name, "")
        if field_name == "promise_amount":
            old_cmp = float(old_raw or 0)
            new_cmp = float(new_raw or 0)
        else:
            old_cmp = (old_raw or "").strip() if isinstance(old_raw, str) else old_raw
            new_cmp = (new_raw or "").strip() if isinstance(new_raw, str) else new_raw
        if old_cmp != new_cmp:
            changes.append(
                (
                    field_name,
                    _format_promise_field(field_name, old_raw),
                    _format_promise_field(field_name, new_raw),
                )
            )
    return changes


def validate_promise_create_form(data, application: sqlite3.Row) -> tuple[dict | None, str | None]:
    snapshot = promise_snapshot_from_form(data)
    if snapshot["promise_amount"] <= 0 or snapshot["promise_amount"] > MAX_PROMISE_AMOUNT:
        return None, "Enter a valid promise amount greater than zero."
    if len(snapshot["commitment_notes"]) > MAX_PROMISE_NOTES_LENGTH:
        return None, f"Commitment notes must be {MAX_PROMISE_NOTES_LENGTH} characters or fewer."
    try:
        promise_day = date.fromisoformat(snapshot["promise_date"][:10])
    except ValueError:
        return None, "Enter a valid promise date (YYYY-MM-DD)."
    snapshot["promise_date"] = promise_day.isoformat()
    snapshot["promise_status"] = "active"

    outstanding = application["outstanding_balance"]
    if outstanding is not None and snapshot["promise_amount"] > float(outstanding):
        return None, "Promise amount cannot exceed the current outstanding balance."

    conn = get_db_connection()
    cursor = conn.cursor()
    existing = fetch_active_promise(cursor, application["id"])
    conn.close()
    if existing:
        return None, "An active promise already exists. Fulfill, break, or cancel it before creating a new one."

    return snapshot, None


def validate_promise_status_update(
    data,
    promise: sqlite3.Row,
) -> tuple[dict | None, str | None, list[str]]:
    warnings: list[str] = []
    new_status = (data.get("promise_status") or "").strip()
    if new_status not in PROMISE_STATUSES:
        return None, "Select a valid promise status.", warnings
    if new_status not in TERMINAL_PROMISE_STATUSES and new_status != promise["promise_status"]:
        return None, "Use active status only when creating a new promise.", warnings

    current_status = promise["promise_status"]
    if current_status in TERMINAL_PROMISE_STATUSES:
        return None, "This promise is already closed and cannot be changed.", warnings

    if new_status == current_status:
        return None, "No promise status change was detected.", warnings

    if new_status in PROMISE_STATUSES_REQUIRING_CONTEXT:
        context = (data.get("promise_context") or "").strip()
        if not context:
            return None, "Provide governance context for this promise status change.", warnings

    if new_status == "broken" and current_status == "active":
        warnings.append("Broken promise will be logged as a governance event.")

    snapshot = promise_snapshot_from_row(promise)
    snapshot["promise_status"] = new_status
    return snapshot, None, warnings


def group_promise_history(rows: list) -> list[dict]:
    batches: list[dict] = []
    for row in rows:
        batches.append(
            {
                "batch_id": row["batch_id"],
                "actor": row["actor"],
                "created_at": row["created_at"],
                "promise_status": row["promise_status"],
                "status_label": PROMISE_STATUS_LABELS.get(row["promise_status"], row["promise_status"]),
                "promise_amount": row["promise_amount"],
                "promise_date": row["promise_date"],
                "action_type": row["action_type"],
                "context_notes": row["context_notes"] or "",
                "is_critical": bool(row["is_critical"]),
            }
        )
    return batches


def _status_timestamp_field(status: str) -> str | None:
    if status == "fulfilled":
        return "fulfilled_at"
    if status == "broken":
        return "broken_at"
    if status in ("cancelled", "expired"):
        return "cancelled_at"
    return None


def persist_promise_create(
    application_id: int,
    snapshot: dict,
    actor: str,
    *,
    context_notes: str = "",
) -> int:
    batch_id = secrets.token_hex(8)
    gov_tag = governance_context_for_promise_status("active", action="created")
    context_notes = append_governance_context(context_notes, gov_tag)
    audit_context = (context_notes or "")[:1000]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO recovery_promises (
                application_id,
                batch_id,
                promise_amount,
                promise_date,
                promise_status,
                commitment_notes,
                created_by,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, 'active', ?, ?, datetime('now'), datetime('now'))
            """,
            (
                application_id,
                batch_id,
                snapshot["promise_amount"],
                snapshot["promise_date"],
                snapshot["commitment_notes"],
                actor,
            ),
        )
        promise_id = cursor.lastrowid

        insert_promise_history_record(
            cursor,
            promise_id=promise_id,
            application_id=application_id,
            batch_id=batch_id,
            snapshot={**snapshot, "promise_status": "active"},
            actor=actor,
            action_type="promise_created",
            context_notes=audit_context,
            is_critical=0,
        )

        _write_promise_workflow_audit(
            cursor,
            application_id=application_id,
            promise_id=promise_id,
            batch_id=batch_id,
            before={},
            after={**snapshot, "promise_status": "active"},
            actor=actor,
            audit_context=audit_context,
            is_critical=0,
        )

        cursor.execute(
            """
            UPDATE applications
            SET collections_status = CASE
                WHEN collections_status IN ('not_in_collections', 'queued') THEN 'promise_to_pay'
                ELSE collections_status
            END,
            updated_at = datetime('now')
            WHERE id = ?
            """,
            (application_id,),
        )

        commit_connection(conn, operation_name="promise_create_commit")
    except Exception as exc:
        conn.rollback()
        log_workflow_failure(
            "Promise creation failed",
            application_id=application_id,
            actor=actor,
            error=str(exc),
        )
        raise
    finally:
        conn.close()

    log_promise_governance(
        application_id=application_id,
        promise_id=promise_id,
        actor=actor,
        promise_status="active",
        action="created",
    )
    return promise_id


def persist_promise_status_update(
    promise_id: int,
    promise: sqlite3.Row,
    snapshot: dict,
    actor: str,
    *,
    context_notes: str = "",
) -> None:
    before = promise_snapshot_from_row(promise)
    after = dict(snapshot)
    new_status = after["promise_status"]
    batch_id = secrets.token_hex(8)
    is_critical = 1 if new_status in PROMISE_CRITICAL_STATUSES else 0
    gov_tag = governance_context_for_promise_status(new_status, action="updated")
    if gov_tag:
        context_notes = append_governance_context(context_notes, gov_tag)
    audit_context = (context_notes or "")[:1000]
    ts_field = _status_timestamp_field(new_status)
    now_iso = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        update_sql = """
            UPDATE recovery_promises
            SET promise_status = ?, commitment_notes = ?, updated_at = datetime('now')
        """
        params: list = [new_status, after.get("commitment_notes", before["commitment_notes"])]
        if ts_field == "fulfilled_at":
            update_sql += ", fulfilled_at = ?"
            params.append(now_iso)
        elif ts_field == "broken_at":
            update_sql += ", broken_at = ?"
            params.append(now_iso)
        elif ts_field == "cancelled_at":
            update_sql += ", cancelled_at = ?"
            params.append(now_iso)
        update_sql += " WHERE id = ?"
        params.append(promise_id)
        cursor.execute(update_sql, params)

        insert_promise_history_record(
            cursor,
            promise_id=promise_id,
            application_id=promise["application_id"],
            batch_id=batch_id,
            snapshot=after,
            actor=actor,
            action_type=f"promise_{new_status}",
            context_notes=audit_context,
            is_critical=is_critical,
        )

        _write_promise_workflow_audit(
            cursor,
            application_id=promise["application_id"],
            promise_id=promise_id,
            batch_id=batch_id,
            before=before,
            after=after,
            actor=actor,
            audit_context=audit_context,
            is_critical=is_critical,
        )

        commit_connection(conn, operation_name="promise_status_update_commit")
    except Exception as exc:
        conn.rollback()
        log_workflow_failure(
            "Promise status update failed",
            application_id=promise["application_id"],
            actor=actor,
            error=str(exc),
        )
        raise
    finally:
        conn.close()

    log_promise_governance(
        application_id=promise["application_id"],
        promise_id=promise_id,
        actor=actor,
        promise_status=new_status,
        action="updated",
        previous_status=before["promise_status"],
    )
    if is_critical:
        log_governance_event(
            "Critical promise event recorded",
            critical=True,
            application_id=promise["application_id"],
            promise_id=promise_id,
            actor=actor,
            promise_status=new_status,
        )

    if new_status == "broken":
        from constants.governance import GOV_TAG_PROMISE_BROKEN
        from repositories.database import get_db_connection
        from repositories.applications import fetch_application
        from services.operational_events import emit_broken_promise_event

        conn = get_db_connection()
        cursor = conn.cursor()
        application = fetch_application(cursor, promise["application_id"])
        conn.close()
        assigned = application["collections_assigned_to"] if application else None
        emit_broken_promise_event(
            application_id=promise["application_id"],
            actor=actor,
            promise_id=promise_id,
            governance_tag=GOV_TAG_PROMISE_BROKEN,
            assigned_to=assigned,
        )


def expire_stale_active_promises(cursor) -> int:
    """Mark long-overdue active promises as expired (optional maintenance, non-destructive)."""
    cursor.execute(
        """
        UPDATE recovery_promises
        SET promise_status = 'expired',
            cancelled_at = datetime('now'),
            updated_at = datetime('now')
        WHERE promise_status = 'active'
          AND date(promise_date) < date('now', '-60 days')
        """
    )
    return cursor.rowcount


def _write_promise_workflow_audit(
    cursor,
    *,
    application_id: int,
    promise_id: int,
    batch_id: str,
    before: dict,
    after: dict,
    actor: str,
    audit_context: str,
    is_critical: int,
) -> None:
    changes = diff_promise_snapshots(before, after) if before else [
        ("promise_status", "—", _format_promise_field("promise_status", after.get("promise_status")))
    ]
    previous_state = json.dumps(before, sort_keys=True, default=str)
    new_state = json.dumps({**after, "promise_id": promise_id}, sort_keys=True, default=str)
    for field_name, old_value, new_value in changes:
        field_action = PROMISE_FIELD_ACTION_TYPES.get(field_name, "promise_update")
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
                audit_context,
                is_critical,
                None,
            ),
        )
