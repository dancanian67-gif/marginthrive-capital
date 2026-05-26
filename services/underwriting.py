import json
import secrets
import sqlite3

from constants.underwriting import (
    MAX_DECISION_REASON_LENGTH,
    MAX_DECISION_SUMMARY_LENGTH,
    MAX_ESCALATION_REASON_LENGTH,
    MAX_OBSERVATION_LENGTH,
    MAX_UNDERWRITING_NOTES_LENGTH,
    UNDERWRITING_ASSESSMENT_FIELDS,
    UNDERWRITING_ASSESSMENT_RATINGS,
    UNDERWRITING_AUDIT_FIELDS,
    UNDERWRITING_CRITICAL_STATUSES,
    UNDERWRITING_FIELD_ACTION_TYPES,
    UNDERWRITING_STATUSES,
    UNDERWRITING_STATUSES_REQUIRING_ESCALATION_REASON,
    UNDERWRITING_STATUSES_REQUIRING_RATIONALE,
    UNDERWRITING_STATUS_LABELS,
)
from repositories.database import get_db_connection
from repositories.underwriting import insert_underwriting_decision_record
from utils.db_write import commit_connection
from utils.governance import append_governance_context, log_underwriting_governance
from utils.ops_logging import log_governance_event, log_workflow_failure


def underwriting_snapshot_from_row(row: sqlite3.Row | dict) -> dict:
    return {
        "underwriting_status": row["underwriting_status"] or "pending_review",
        "affordability_assessment": row["affordability_assessment"] or "not_assessed",
        "repayment_confidence": row["repayment_confidence"] or "not_assessed",
        "business_stability_review": row["business_stability_review"] or "not_assessed",
        "documentation_quality_review": row["documentation_quality_review"] or "not_assessed",
        "operational_risk_observations": row["operational_risk_observations"] or "",
        "fraud_concern_observations": row["fraud_concern_observations"] or "",
        "underwriting_notes": row["underwriting_notes"] or "",
        "decision_summary": row["decision_summary"] or "",
        "decision_reason": row["decision_reason"] or "",
        "escalation_reason": row["escalation_reason"] or "",
        "reviewed_by": row["reviewed_by"] or "",
    }


def underwriting_snapshot_from_form(data, reviewed_by: str) -> dict:
    return {
        "underwriting_status": (data.get("underwriting_status") or "").strip(),
        "affordability_assessment": (data.get("affordability_assessment") or "not_assessed").strip(),
        "repayment_confidence": (data.get("repayment_confidence") or "not_assessed").strip(),
        "business_stability_review": (data.get("business_stability_review") or "not_assessed").strip(),
        "documentation_quality_review": (data.get("documentation_quality_review") or "not_assessed").strip(),
        "operational_risk_observations": (data.get("operational_risk_observations") or "").strip(),
        "fraud_concern_observations": (data.get("fraud_concern_observations") or "").strip(),
        "underwriting_notes": (data.get("underwriting_notes") or "").strip(),
        "decision_summary": (data.get("decision_summary") or "").strip(),
        "decision_reason": (data.get("decision_reason") or "").strip(),
        "escalation_reason": (data.get("escalation_reason") or "").strip(),
        "reviewed_by": reviewed_by,
    }


def _format_underwriting_field(field_name: str, value) -> str:
    if field_name == "underwriting_status":
        return UNDERWRITING_STATUS_LABELS.get(value, str(value or "—"))
    if field_name in UNDERWRITING_ASSESSMENT_FIELDS:
        from constants.underwriting import UNDERWRITING_ASSESSMENT_LABELS

        return UNDERWRITING_ASSESSMENT_LABELS.get(value, str(value or "—"))
    text = (value or "").strip()
    return text if text else "—"


def diff_underwriting_snapshots(before: dict, after: dict) -> list[tuple[str, str, str]]:
    changes: list[tuple[str, str, str]] = []
    for field_name in UNDERWRITING_AUDIT_FIELDS:
        old_raw = before.get(field_name, "")
        new_raw = after.get(field_name, "")
        old_cmp = (old_raw or "").strip()
        new_cmp = (new_raw or "").strip()
        if old_cmp != new_cmp:
            changes.append(
                (
                    field_name,
                    _format_underwriting_field(field_name, old_raw),
                    _format_underwriting_field(field_name, new_raw),
                )
            )
    return changes


def validate_underwriting_form(data, current: sqlite3.Row | None = None) -> tuple[dict | None, str | None]:
    reviewed_by = (data.get("reviewed_by") or "").strip()
    snapshot = underwriting_snapshot_from_form(data, reviewed_by)

    if snapshot["underwriting_status"] not in UNDERWRITING_STATUSES:
        return None, "Select a valid financing decision status."

    for field_name in UNDERWRITING_ASSESSMENT_FIELDS:
        if snapshot[field_name] not in UNDERWRITING_ASSESSMENT_RATINGS:
            return None, f"Select a valid rating for {field_name.replace('_', ' ')}."

    if len(snapshot["underwriting_notes"]) > MAX_UNDERWRITING_NOTES_LENGTH:
        return None, f"Underwriting notes must be {MAX_UNDERWRITING_NOTES_LENGTH} characters or fewer."
    if len(snapshot["decision_summary"]) > MAX_DECISION_SUMMARY_LENGTH:
        return None, f"Decision summary must be {MAX_DECISION_SUMMARY_LENGTH} characters or fewer."
    if len(snapshot["decision_reason"]) > MAX_DECISION_REASON_LENGTH:
        return None, f"Decision reason must be {MAX_DECISION_REASON_LENGTH} characters or fewer."
    if len(snapshot["escalation_reason"]) > MAX_ESCALATION_REASON_LENGTH:
        return None, f"Escalation reason must be {MAX_ESCALATION_REASON_LENGTH} characters or fewer."
    if len(snapshot["operational_risk_observations"]) > MAX_OBSERVATION_LENGTH:
        return None, f"Operational risk observations must be {MAX_OBSERVATION_LENGTH} characters or fewer."
    if len(snapshot["fraud_concern_observations"]) > MAX_OBSERVATION_LENGTH:
        return None, f"Fraud concern observations must be {MAX_OBSERVATION_LENGTH} characters or fewer."

    if snapshot["underwriting_status"] in UNDERWRITING_STATUSES_REQUIRING_RATIONALE:
        if not snapshot["decision_summary"] and not snapshot["decision_reason"]:
            return (
                None,
                "Provide a decision summary or decision reason for this financing decision.",
            )

    if snapshot["underwriting_status"] in UNDERWRITING_STATUSES_REQUIRING_ESCALATION_REASON:
        if not snapshot["escalation_reason"]:
            return None, "Escalation reason is required when status is Escalated review."

    if current is not None:
        before = underwriting_snapshot_from_row(current)
        if before == snapshot:
            return None, "No underwriting changes were detected."

    return snapshot, None


def group_underwriting_decision_history(rows: list) -> list[dict]:
    batches: list[dict] = []
    index_by_batch: dict[str, int] = {}

    for row in rows:
        batch_id = row["batch_id"]
        status_label = UNDERWRITING_STATUS_LABELS.get(
            row["underwriting_status"],
            row["underwriting_status"],
        )
        headline = row["decision_summary"] or row["decision_reason"] or status_label
        entry = {
            "underwriting_status": row["underwriting_status"],
            "status_label": status_label,
            "headline": headline,
            "reviewed_by": row["reviewed_by"],
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
                    "decision_summary": row["decision_summary"] or "",
                    "decision_reason": row["decision_reason"] or "",
                    "escalation_reason": row["escalation_reason"] or "",
                    "underwriting_notes": row["underwriting_notes"] or "",
                    "underwriting_status": row["underwriting_status"],
                    "status_label": status_label,
                    "headline": headline,
                    "reviewed_by": row["reviewed_by"],
                    "is_critical": entry["is_critical"],
                }
            )
    return batches


def persist_underwriting_update(
    application_id: int,
    application: sqlite3.Row,
    snapshot: dict,
    actor: str,
    *,
    context_notes: str = "",
) -> None:
    before = underwriting_snapshot_from_row(application)
    after = dict(snapshot)
    changes = diff_underwriting_snapshots(before, after)
    if not changes:
        return

    batch_id = secrets.token_hex(8)
    is_critical = 1 if after["underwriting_status"] in UNDERWRITING_CRITICAL_STATUSES else 0
    reviewed_at_expr = "datetime('now')"
    previous_status = before.get("underwriting_status")
    if after["underwriting_status"] in UNDERWRITING_CRITICAL_STATUSES:
        from constants.governance import GOV_TAG_UNDERWRITING_ESCALATION, GOV_TAG_UNDERWRITING_REJECTION

        tag = (
            GOV_TAG_UNDERWRITING_REJECTION
            if after["underwriting_status"] == "rejected"
            else GOV_TAG_UNDERWRITING_ESCALATION
        )
        context_notes = append_governance_context(context_notes, tag)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            UPDATE applications
            SET
                underwriting_status = ?,
                affordability_assessment = ?,
                repayment_confidence = ?,
                business_stability_review = ?,
                documentation_quality_review = ?,
                operational_risk_observations = ?,
                fraud_concern_observations = ?,
                underwriting_notes = ?,
                decision_summary = ?,
                decision_reason = ?,
                escalation_reason = ?,
                reviewed_by = ?,
                reviewed_at = {reviewed_at_expr},
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                after["underwriting_status"],
                after["affordability_assessment"],
                after["repayment_confidence"],
                after["business_stability_review"],
                after["documentation_quality_review"],
                after["operational_risk_observations"],
                after["fraud_concern_observations"],
                after["underwriting_notes"],
                after["decision_summary"],
                after["decision_reason"],
                after["escalation_reason"],
                after["reviewed_by"],
                application_id,
            ),
        )

        insert_underwriting_decision_record(
            cursor,
            application_id=application_id,
            batch_id=batch_id,
            snapshot=after,
            actor=actor,
            reviewed_by=after["reviewed_by"],
            context_notes=context_notes,
            is_critical=is_critical,
        )

        previous_state = json.dumps({**before, "reviewed_by": before.get("reviewed_by", "")}, sort_keys=True)
        new_state = json.dumps(after, sort_keys=True)
        for field_name, old_value, new_value in changes:
            field_critical = (
                1
                if field_name == "underwriting_status"
                and after["underwriting_status"] in UNDERWRITING_CRITICAL_STATUSES
                else 0
            )
            field_action = UNDERWRITING_FIELD_ACTION_TYPES.get(field_name, "underwriting_update")
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
                    field_critical,
                    None,
                ),
            )

        commit_connection(conn, operation_name="underwriting_update_commit")
    except Exception as exc:
        conn.rollback()
        log_workflow_failure(
            "Underwriting persistence failed",
            application_id=application_id,
            actor=actor,
            error=str(exc),
        )
        raise
    finally:
        conn.close()

    log_underwriting_governance(
        application_id=application_id,
        actor=actor,
        underwriting_status=after["underwriting_status"],
        previous_status=previous_status,
    )

    if after["underwriting_status"] != previous_status:
        from constants.governance import GOV_TAG_UNDERWRITING_ESCALATION, GOV_TAG_UNDERWRITING_REJECTION
        from services.operational_events import emit_underwriting_decision_event, session_operator_id

        gov_tag = None
        if after["underwriting_status"] == "rejected":
            gov_tag = GOV_TAG_UNDERWRITING_REJECTION
        elif after["underwriting_status"] in UNDERWRITING_CRITICAL_STATUSES:
            gov_tag = GOV_TAG_UNDERWRITING_ESCALATION
        emit_underwriting_decision_event(
            application_id=application_id,
            actor=actor,
            operator_id=session_operator_id(),
            underwriting_status=after["underwriting_status"],
            governance_tag=gov_tag,
            batch_id=batch_id,
        )


def financing_rationale_summary(application: sqlite3.Row | dict) -> str:
    status = application["underwriting_status"]
    status_label = UNDERWRITING_STATUS_LABELS.get(status, status)
    parts = [status_label]
    if application["decision_summary"]:
        parts.append(application["decision_summary"])
    elif application["decision_reason"]:
        parts.append(application["decision_reason"])
    if status == "escalated_review" and application["escalation_reason"]:
        parts.append(f"Escalation: {application['escalation_reason']}")
    return " — ".join(parts)
