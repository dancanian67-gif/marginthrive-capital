"""Collections operations workspace service layer (Phase F1)."""

from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import date

from constants.collections import (
    DELINQUENCY_BUCKETS,
    COLLECTIONS_AUDIT_FIELDS,
    COLLECTIONS_CRITICAL_STATUSES,
    COLLECTIONS_FIELD_ACTION_TYPES,
    COLLECTIONS_PAGE_SIZE,
    COLLECTIONS_PRIORITIES,
    COLLECTIONS_RISK_LEVELS,
    COLLECTIONS_SENSITIVE_STATUSES,
    COLLECTIONS_STATUSES,
    COLLECTIONS_STATUSES_REQUIRING_CONTEXT,
    COLLECTIONS_STATUS_LABELS,
    COLLECTIONS_PRIORITY_LABELS,
    COLLECTIONS_RISK_LABELS,
    DEFAULT_COLLECTIONS_PRIORITY,
    DEFAULT_COLLECTIONS_RISK_LEVEL,
    DEFAULT_COLLECTIONS_STATUS,
    MAX_COLLECTIONS_ASSIGNED_LENGTH,
    MAX_COLLECTIONS_NOTES_LENGTH,
)
from repositories.collections import (
    fetch_collections_history_rows,
    insert_collections_history_record,
)
from repositories.database import get_db_connection
from services.delinquency import enrich_collections_queue_row
from utils.db_write import commit_connection
from utils.governance import (
    append_governance_context,
    governance_context_for_collections_status,
    log_collections_governance,
)
from utils.ops_logging import log_governance_event, log_workflow_failure


def collections_snapshot_from_row(row: sqlite3.Row | dict) -> dict:
    return {
        "collections_status": row["collections_status"] or DEFAULT_COLLECTIONS_STATUS,
        "collections_priority": row["collections_priority"] or DEFAULT_COLLECTIONS_PRIORITY,
        "collections_assigned_to": (row["collections_assigned_to"] or "").strip(),
        "collections_last_contact_at": (row["collections_last_contact_at"] or "").strip() or None,
        "collections_next_follow_up": (row["collections_next_follow_up"] or "").strip() or None,
        "collections_notes_summary": (row["collections_notes_summary"] or "").strip(),
        "collections_risk_level": row["collections_risk_level"] or DEFAULT_COLLECTIONS_RISK_LEVEL,
    }


def collections_snapshot_from_form(data) -> dict:
    return {
        "collections_status": (data.get("collections_status") or "").strip(),
        "collections_priority": (data.get("collections_priority") or DEFAULT_COLLECTIONS_PRIORITY).strip(),
        "collections_assigned_to": (data.get("collections_assigned_to") or "").strip(),
        "collections_last_contact_at": (data.get("collections_last_contact_at") or "").strip() or None,
        "collections_next_follow_up": (data.get("collections_next_follow_up") or "").strip() or None,
        "collections_notes_summary": (data.get("collections_notes_summary") or "").strip(),
        "collections_risk_level": (data.get("collections_risk_level") or DEFAULT_COLLECTIONS_RISK_LEVEL).strip(),
    }


def _format_collections_field(field_name: str, value) -> str:
    if field_name == "collections_status":
        return COLLECTIONS_STATUS_LABELS.get(str(value or ""), str(value or "—"))
    if field_name == "collections_priority":
        return COLLECTIONS_PRIORITY_LABELS.get(str(value or ""), str(value or "—"))
    if field_name == "collections_risk_level":
        return COLLECTIONS_RISK_LABELS.get(str(value or ""), str(value or "—"))
    text = (value or "").strip() if isinstance(value, str) else value
    return str(text) if text not in (None, "") else "—"


def diff_collections_snapshots(before: dict, after: dict) -> list[tuple[str, str, str]]:
    changes: list[tuple[str, str, str]] = []
    for field_name in COLLECTIONS_AUDIT_FIELDS:
        old_raw = before.get(field_name, "")
        new_raw = after.get(field_name, "")
        old_cmp = (old_raw or "").strip() if isinstance(old_raw, str) else old_raw
        new_cmp = (new_raw or "").strip() if isinstance(new_raw, str) else new_raw
        if old_cmp != new_cmp:
            changes.append(
                (
                    field_name,
                    _format_collections_field(field_name, old_raw),
                    _format_collections_field(field_name, new_raw),
                )
            )
    return changes


def _parse_optional_date(value: str | None, field_label: str) -> tuple[str | None, str | None]:
    raw = (value or "").strip()
    if not raw:
        return None, None
    try:
        return date.fromisoformat(raw[:10]).isoformat(), None
    except ValueError:
        return None, f"Enter a valid {field_label} (YYYY-MM-DD)."


def validate_collections_transition(before: dict, after: dict) -> list[str]:
    """Non-blocking operational warnings for questionable collections transitions."""
    warnings: list[str] = []
    old_status = before["collections_status"]
    new_status = after["collections_status"]

    if new_status == "resolved" and old_status not in ("resolved", "not_in_collections"):
        if new_status != old_status:
            warnings.append(
                "Resolved status recorded — confirm outstanding balance and loan lifecycle are accurate."
            )

    if new_status in COLLECTIONS_SENSITIVE_STATUSES and old_status == "not_in_collections":
        warnings.append(
            f"Account moved directly to “{COLLECTIONS_STATUS_LABELS.get(new_status, new_status)}” "
            "without prior queue status."
        )

    if (
        after["collections_next_follow_up"]
        and before.get("collections_next_follow_up") == after["collections_next_follow_up"]
        and before == after
    ):
        pass
    elif (
        after["collections_next_follow_up"]
        and before.get("collections_next_follow_up") == after["collections_next_follow_up"]
        and new_status == old_status
    ):
        warnings.append("Follow-up date unchanged — duplicate scheduling avoided.")

    if after["collections_assigned_to"] and not after["collections_assigned_to"].strip():
        warnings.append("Collections assignment cleared — case is now unassigned.")

    old_assignee = (before.get("collections_assigned_to") or "").strip()
    new_assignee = (after.get("collections_assigned_to") or "").strip()
    if old_assignee and new_assignee and old_assignee != new_assignee:
        warnings.append(f"Ownership transferred from “{old_assignee}” to “{new_assignee}”.")

    return warnings


def validate_collections_form(
    data,
    current: sqlite3.Row | None = None,
) -> tuple[dict | None, str | None, list[str]]:
    snapshot = collections_snapshot_from_form(data)
    warnings: list[str] = []

    if snapshot["collections_status"] not in COLLECTIONS_STATUSES:
        return None, "Select a valid collections status.", warnings

    if snapshot["collections_priority"] not in COLLECTIONS_PRIORITIES:
        return None, "Select a valid collections priority.", warnings

    if snapshot["collections_risk_level"] not in COLLECTIONS_RISK_LEVELS:
        return None, "Select a valid collections risk level.", warnings

    if len(snapshot["collections_assigned_to"]) > MAX_COLLECTIONS_ASSIGNED_LENGTH:
        return (
            None,
            f"Assigned officer name must be {MAX_COLLECTIONS_ASSIGNED_LENGTH} characters or fewer.",
            warnings,
        )

    if len(snapshot["collections_notes_summary"]) > MAX_COLLECTIONS_NOTES_LENGTH:
        return None, f"Recovery notes must be {MAX_COLLECTIONS_NOTES_LENGTH} characters or fewer.", warnings

    last_contact, err = _parse_optional_date(snapshot["collections_last_contact_at"], "last contact date")
    if err:
        return None, err, warnings
    snapshot["collections_last_contact_at"] = last_contact

    follow_up, err = _parse_optional_date(snapshot["collections_next_follow_up"], "follow-up date")
    if err:
        return None, err, warnings
    snapshot["collections_next_follow_up"] = follow_up

    if snapshot["collections_status"] in COLLECTIONS_STATUSES_REQUIRING_CONTEXT:
        context = (data.get("collections_context") or "").strip()
        if not context and not snapshot["collections_notes_summary"]:
            return (
                None,
                "Provide recovery context notes for this collections action.",
                warnings,
            )

    if current is not None and int(current["flagged_fraud"] or 0) == 1:
        if snapshot["collections_status"] in COLLECTIONS_SENSITIVE_STATUSES.union({"resolved"}):
            context = (data.get("collections_context") or "").strip()
            if not context:
                return (
                    None,
                    "Fraud-flagged accounts require governance context for this recovery action.",
                    warnings,
                )
            warnings.append(
                "Fraud-flagged account — recovery action will be tagged for governance review."
            )

    if current is not None:
        before = collections_snapshot_from_row(current)
        if before == snapshot:
            return None, "No collections changes were detected.", warnings
        warnings.extend(validate_collections_transition(before, snapshot))

    return snapshot, None, warnings


def group_collections_history(rows: list) -> list[dict]:
    batches: list[dict] = []
    index_by_batch: dict[str, int] = {}

    for row in rows:
        batch_id = row["batch_id"]
        status_label = COLLECTIONS_STATUS_LABELS.get(
            row["collections_status"],
            row["collections_status"],
        )
        entry = {
            "collections_status": row["collections_status"],
            "status_label": status_label,
            "collections_priority": row["collections_priority"],
            "collections_assigned_to": row["collections_assigned_to"],
            "is_critical": bool(row["is_critical"]),
        }
        if batch_id in index_by_batch:
            batches[index_by_batch[batch_id]]["is_critical"] = (
                batches[index_by_batch[batch_id]]["is_critical"] or entry["is_critical"]
            )
        else:
            index_by_batch[batch_id] = len(batches)
            batches.append(
                {
                    "batch_id": batch_id,
                    "actor": row["actor"],
                    "created_at": row["created_at"],
                    "context_notes": row["context_notes"] or "",
                    "action_type": row["action_type"],
                    "status_label": status_label,
                    "collections_priority": row["collections_priority"],
                    "collections_assigned_to": row["collections_assigned_to"],
                    "collections_risk_level": row["collections_risk_level"],
                    "is_critical": entry["is_critical"],
                }
            )
    return batches


def persist_collections_update(
    application_id: int,
    application: sqlite3.Row,
    snapshot: dict,
    actor: str,
    *,
    context_notes: str = "",
) -> None:
    before = collections_snapshot_from_row(application)
    after = dict(snapshot)
    changes = diff_collections_snapshots(before, after)
    if not changes:
        return

    batch_id = secrets.token_hex(8)
    is_critical = 1 if after["collections_status"] in COLLECTIONS_CRITICAL_STATUSES else 0
    if after["collections_status"] == "resolved":
        is_critical = 1
    gov_tag = governance_context_for_collections_status(
        after["collections_status"],
        flagged_fraud=bool(application["flagged_fraud"]),
    )
    if gov_tag:
        context_notes = append_governance_context(context_notes, gov_tag)
    audit_context = (context_notes or "")[:1000]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE applications
            SET
                collections_status = ?,
                collections_priority = ?,
                collections_assigned_to = ?,
                collections_last_contact_at = ?,
                collections_next_follow_up = ?,
                collections_notes_summary = ?,
                collections_risk_level = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                after["collections_status"],
                after["collections_priority"],
                after["collections_assigned_to"],
                after["collections_last_contact_at"],
                after["collections_next_follow_up"],
                after["collections_notes_summary"],
                after["collections_risk_level"],
                application_id,
            ),
        )

        insert_collections_history_record(
            cursor,
            application_id=application_id,
            batch_id=batch_id,
            snapshot=after,
            actor=actor,
            action_type="collections_update",
            context_notes=audit_context,
            is_critical=is_critical,
        )

        previous_state = json.dumps(before, sort_keys=True, default=str)
        new_state = json.dumps(after, sort_keys=True, default=str)
        for field_name, old_value, new_value in changes:
            field_critical = (
                1
                if field_name == "collections_status"
                and after["collections_status"] in COLLECTIONS_CRITICAL_STATUSES
                else 0
            )
            field_action = COLLECTIONS_FIELD_ACTION_TYPES.get(field_name, "collections_update")
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
                    field_critical,
                    None,
                ),
            )

        commit_connection(conn, operation_name="collections_update_commit")
    except Exception as exc:
        conn.rollback()
        log_workflow_failure(
            "Collections update persistence failed",
            application_id=application_id,
            actor=actor,
            error=str(exc),
        )
        raise
    finally:
        conn.close()

    log_collections_governance(
        application_id=application_id,
        actor=actor,
        collections_status=after["collections_status"],
        previous_status=before["collections_status"],
    )
    if is_critical:
        log_governance_event(
            "Critical collections event recorded",
            critical=True,
            application_id=application_id,
            actor=actor,
            collections_status=after["collections_status"],
            batch_id=batch_id,
        )

    if after["collections_status"] != before["collections_status"]:
        from constants.collections import COLLECTIONS_SENSITIVE_STATUSES
        from services.operational_events import emit_collections_escalation_event

        if (
            after["collections_status"] in COLLECTIONS_CRITICAL_STATUSES
            or after["collections_status"] in COLLECTIONS_SENSITIVE_STATUSES
        ):
            emit_collections_escalation_event(
                application_id=application_id,
                actor=actor,
                collections_status=after["collections_status"],
                governance_tag=gov_tag,
                assigned_to=after.get("collections_assigned_to"),
            )


def parse_collections_list_filters(args) -> dict:
    status = (args.get("collections_status") or "").strip()
    if status and status not in COLLECTIONS_STATUSES:
        status = ""

    priority = (args.get("collections_priority") or "").strip()
    if priority and priority not in COLLECTIONS_PRIORITIES:
        priority = ""

    risk = (args.get("collections_risk_level") or "").strip()
    if risk and risk not in COLLECTIONS_RISK_LEVELS:
        risk = ""

    assigned = (args.get("collections_assigned_to") or "").strip()
    if len(assigned) > MAX_COLLECTIONS_ASSIGNED_LENGTH:
        assigned = assigned[:MAX_COLLECTIONS_ASSIGNED_LENGTH]

    bucket = (args.get("delinquency_bucket") or "").strip()
    if bucket and bucket not in DELINQUENCY_BUCKETS:
        bucket = ""

    search = (args.get("q") or "").strip()[:200]

    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    promise_filter = (args.get("promise_filter") or "").strip()
    from constants.promises import PROMISE_QUEUE_FILTERS

    if promise_filter and promise_filter not in PROMISE_QUEUE_FILTERS:
        promise_filter = ""

    return {
        "collections_status": status,
        "collections_priority": priority,
        "collections_assigned_to": assigned,
        "collections_risk_level": risk,
        "delinquency_bucket": bucket,
        "promise_filter": promise_filter,
        "q": search,
        "page": page,
    }


def collections_filters_to_query_params(filters: dict) -> dict:
    params = {}
    for key in (
        "collections_status",
        "collections_priority",
        "collections_assigned_to",
        "collections_risk_level",
        "delinquency_bucket",
        "promise_filter",
        "q",
        "page",
    ):
        value = filters.get(key)
        if value:
            params[key] = value
    return params


def build_collections_page(cursor, filters: dict) -> dict:
    from repositories.collections import count_collections_queue
    from repositories.collections_intelligence import (
        fetch_application_intelligence_context,
        fetch_collections_queue_intelligence_sorted,
    )
    from services.delinquency import enrich_collections_queue_row_with_intelligence

    total = count_collections_queue(cursor, filters)
    page = filters.get("page", 1)
    offset = (page - 1) * COLLECTIONS_PAGE_SIZE
    rows = fetch_collections_queue_intelligence_sorted(
        cursor,
        filters,
        limit=COLLECTIONS_PAGE_SIZE,
        offset=offset,
    )
    app_ids = [row["id"] for row in rows]
    intel_by_app = fetch_application_intelligence_context(cursor, app_ids)
    from repositories.promises import fetch_promise_summaries_for_applications

    promise_by_app = fetch_promise_summaries_for_applications(cursor, app_ids)
    queue = []
    for row in rows:
        app_id = row["id"]
        ctx = dict(intel_by_app.get(app_id) or {})
        ctx["promise_summary"] = promise_by_app.get(app_id, {})
        queue.append(enrich_collections_queue_row_with_intelligence(row, ctx))
    total_pages = max(1, (total + COLLECTIONS_PAGE_SIZE - 1) // COLLECTIONS_PAGE_SIZE)
    return {
        "queue": queue,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "page_size": COLLECTIONS_PAGE_SIZE,
    }
