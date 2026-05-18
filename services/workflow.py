import sqlite3

from constants.workflow import (
    APPLICATION_RISK_LEVELS,
    APPLICATION_STATUSES,
    APPLICATION_SUB_STATUSES,
    DEFAULT_APPLICATION_STATUS,
    KPI_ACTIVE_PIPELINE_STATUSES,
    KPI_APPROVED_STATUSES,
    KPI_HIGH_RISK_LEVELS,
    KPI_OPS_REVIEW_SUB_STATUS,
    KPI_REJECTED_STATUS,
    MAX_APPROVAL_NOTES_LENGTH,
)
from repositories.officers import normalize_officer_name


def normalize_sub_status(raw_value: str) -> str | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    return value if value in APPLICATION_SUB_STATUSES else None


def parse_flagged_fraud(raw_value: str) -> int:
    return 1 if (raw_value or "").strip() in {"1", "true", "on", "yes"} else 0


def is_allowed_status_transition(current_status: str, next_status: str) -> bool:
    if current_status == next_status:
        return True

    if current_status == KPI_REJECTED_STATUS:
        return next_status in {KPI_REJECTED_STATUS, DEFAULT_APPLICATION_STATUS}

    if current_status == "Loan issued":
        return next_status in {"Loan issued", "Pending payments", KPI_REJECTED_STATUS}

    if next_status == "Loan issued":
        return current_status in {"Pending payments", "Loan issued"}

    if next_status == "Pending payments":
        return current_status in {
            "Signing agreement",
            "Final review",
            "Pending payments",
            "Loan issued",
        }

    if current_status == "Loan issued" and next_status in KPI_ACTIVE_PIPELINE_STATUSES:
        return False

    return True


def next_pipeline_status(current_status: str) -> str | None:
    if current_status not in KPI_ACTIVE_PIPELINE_STATUSES:
        return None
    index = APPLICATION_STATUSES.index(current_status)
    if index + 1 < len(APPLICATION_STATUSES):
        candidate = APPLICATION_STATUSES[index + 1]
        if candidate in KPI_ACTIVE_PIPELINE_STATUSES:
            return candidate
    return None


def workflow_row_signature(row: sqlite3.Row) -> tuple:
    return (
        row["status"],
        row["sub_status"],
        row["risk_level"],
        row["assigned_officer"] or "",
        row["approval_notes"] or "",
        int(row["flagged_fraud"] or 0),
    )


def validate_workflow_form(data, current: sqlite3.Row | None = None) -> tuple[dict | None, str | None]:
    status = (data.get("status") or "").strip()
    if status not in APPLICATION_STATUSES:
        return None, "Select a valid workflow status."

    sub_status = normalize_sub_status(data.get("sub_status", ""))
    if (data.get("sub_status") or "").strip() and sub_status is None:
        return None, "Select a valid sub-status or leave it blank."

    risk_level = (data.get("risk_level") or "").strip()
    if risk_level not in APPLICATION_RISK_LEVELS:
        return None, "Select a valid risk level."

    assigned_officer = normalize_officer_name(data.get("assigned_officer", ""))
    if (data.get("assigned_officer") or "").strip() and not assigned_officer:
        return None, "Officer name can only include letters, numbers, spaces, and . ' -"

    approval_notes = (data.get("approval_notes") or "").strip()
    if len(approval_notes) > MAX_APPROVAL_NOTES_LENGTH:
        return None, f"Notes must be {MAX_APPROVAL_NOTES_LENGTH} characters or fewer."

    if current is not None and not is_allowed_status_transition(current["status"], status):
        return (
            None,
            f"Cannot move directly from “{current['status']}” to “{status}”. "
            "Use an allowed intermediate stage or reopen from Rejected.",
        )

    workflow = {
        "status": status,
        "sub_status": sub_status,
        "risk_level": risk_level,
        "assigned_officer": assigned_officer,
        "approval_notes": approval_notes,
        "flagged_fraud": parse_flagged_fraud(data.get("flagged_fraud", "")),
    }

    if current is not None:
        proposed = (
            workflow["status"],
            workflow["sub_status"],
            workflow["risk_level"],
            workflow["assigned_officer"],
            workflow["approval_notes"],
            workflow["flagged_fraud"],
        )
        if proposed == workflow_row_signature(current):
            return None, "No workflow changes were detected."

    return workflow, None


def apply_workflow_quick_action(form_data, current: sqlite3.Row) -> tuple[dict | None, str | None]:
    action = (form_data.get("workflow_action") or "").strip()
    if not action:
        return None, None

    payload = {
        "status": current["status"],
        "sub_status": current["sub_status"] or "",
        "risk_level": current["risk_level"],
        "assigned_officer": current["assigned_officer"] or "",
        "approval_notes": current["approval_notes"] or "",
        "flagged_fraud": "1" if current["flagged_fraud"] else "",
    }

    if action == "advance_status":
        next_status = next_pipeline_status(current["status"])
        if not next_status:
            return None, "This application is not in a stage that can be advanced."
        payload["status"] = next_status
        payload["sub_status"] = ""
    elif action == "margin_to_act":
        payload["sub_status"] = KPI_OPS_REVIEW_SUB_STATUS
    elif action == "clear_sub_status":
        payload["sub_status"] = ""
    elif action == "mark_high_risk":
        payload["risk_level"] = "High"
    elif action == "clear_fraud_flag":
        payload["flagged_fraud"] = ""
    else:
        return None, "Unknown quick action."

    return validate_workflow_form(payload, current)


def application_needs_attention(row) -> bool:
    if row["flagged_fraud"]:
        return True
    if row["risk_level"] in KPI_HIGH_RISK_LEVELS:
        return True
    if row["sub_status"] == KPI_OPS_REVIEW_SUB_STATUS:
        return True
    if row["status"] in KPI_ACTIVE_PIPELINE_STATUSES and not (row["assigned_officer"] or "").strip():
        return True
