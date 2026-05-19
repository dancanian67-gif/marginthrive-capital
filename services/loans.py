import json
import secrets
import sqlite3
from datetime import date, datetime

from constants.loans import (
    ACTIVE_LOAN_LIFECYCLE_STATUSES,
    DEFAULT_LOAN_LIFECYCLE_STATUS,
    LOAN_ACCOUNT_AUDIT_FIELDS,
    LOAN_LIFECYCLE_STATUSES,
    LOAN_FIELD_ACTION_TYPES,
    LOAN_LIFECYCLE_CRITICAL_STATUSES,
    LOAN_LIFECYCLE_STATUS_LABELS,
    LOAN_STATUSES_REQUIRING_COLLECTIONS_NOTE,
    MAX_COLLECTIONS_NOTES_LENGTH,
    MAX_LOAN_ACCOUNT_CONTEXT_LENGTH,
    MAX_LOAN_ACCOUNT_NUMBER_LENGTH,
    MAX_MISSED_PAYMENT_OBSERVATIONS_LENGTH,
    MAX_REPAYMENT_NOTES_LENGTH,
    REPAYMENT_FREQUENCIES,
    REPAYMENT_FREQUENCY_LABELS,
    REPAYMENT_RISK_LABELS,
    REPAYMENT_RISK_LEVELS,
    SERVICING_LOAN_LIFECYCLE_STATUSES,
    TERMINAL_LOAN_LIFECYCLE_STATUSES,
    UNDERWRITING_STATUSES_ELIGIBLE_FOR_LOAN_ACTIVATION,
)
from repositories.database import get_db_connection
from repositories.loans import insert_loan_account_history_record, insert_repayment_record
from utils.ops_logging import log_governance_event, log_workflow_failure


def compute_repayment_progress(issued_amount: float | None, outstanding_balance: float | None) -> float:
    if issued_amount is None or issued_amount <= 0:
        return 0.0
    outstanding = outstanding_balance if outstanding_balance is not None else issued_amount
    outstanding = max(0.0, min(float(outstanding), float(issued_amount)))
    return round(((float(issued_amount) - outstanding) / float(issued_amount)) * 100, 1)


def generate_loan_account_number(application_id: int) -> str:
    year = datetime.utcnow().year
    return f"MT-{year}-{application_id:05d}"


def _parse_optional_float(value: str | None) -> float | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def loan_snapshot_from_row(row: sqlite3.Row | dict) -> dict:
    issued = row["issued_amount"]
    outstanding = row["outstanding_balance"]
    progress = row["repayment_progress"]
    if progress is None or progress == "":
        progress = compute_repayment_progress(issued, outstanding)
    return {
        "loan_lifecycle_status": row["loan_lifecycle_status"] or DEFAULT_LOAN_LIFECYCLE_STATUS,
        "loan_account_number": (row["loan_account_number"] or "").strip(),
        "issued_amount": issued,
        "outstanding_balance": outstanding,
        "repayment_progress": float(progress or 0),
        "issue_date": (row["issue_date"] or "").strip() or None,
        "due_date": (row["due_date"] or "").strip() or None,
        "installment_amount": row["installment_amount"],
        "repayment_frequency": (row["repayment_frequency"] or "").strip(),
        "collections_notes": (row["collections_notes"] or "").strip(),
        "missed_payment_observations": (row["missed_payment_observations"] or "").strip(),
        "repayment_risk_level": row["repayment_risk_level"] or "current",
    }


def loan_snapshot_from_form(data) -> dict:
    issued = _parse_optional_float(data.get("issued_amount"))
    outstanding = _parse_optional_float(data.get("outstanding_balance"))
    if outstanding is None and issued is not None:
        outstanding = issued
    progress = compute_repayment_progress(issued, outstanding)
    return {
        "loan_lifecycle_status": (data.get("loan_lifecycle_status") or "").strip(),
        "loan_account_number": (data.get("loan_account_number") or "").strip(),
        "issued_amount": issued,
        "outstanding_balance": outstanding,
        "repayment_progress": progress,
        "issue_date": (data.get("issue_date") or "").strip() or None,
        "due_date": (data.get("due_date") or "").strip() or None,
        "installment_amount": _parse_optional_float(data.get("installment_amount")),
        "repayment_frequency": (data.get("repayment_frequency") or "").strip(),
        "collections_notes": (data.get("collections_notes") or "").strip(),
        "missed_payment_observations": (data.get("missed_payment_observations") or "").strip(),
        "repayment_risk_level": (data.get("repayment_risk_level") or "current").strip(),
    }


def _format_loan_field(field_name: str, value) -> str:
    if field_name == "loan_lifecycle_status":
        return LOAN_LIFECYCLE_STATUS_LABELS.get(str(value or ""), str(value or "—"))
    if field_name == "repayment_frequency":
        return REPAYMENT_FREQUENCY_LABELS.get(str(value or ""), str(value or "—"))
    if field_name == "repayment_risk_level":
        return REPAYMENT_RISK_LABELS.get(str(value or ""), str(value or "—"))
    if field_name in {"issued_amount", "outstanding_balance", "installment_amount", "repayment_progress"}:
        if value is None or value == "":
            return "—"
        return str(value)
    text = (value or "").strip() if isinstance(value, str) else value
    return str(text) if text not in (None, "") else "—"


def diff_loan_snapshots(before: dict, after: dict) -> list[tuple[str, str, str]]:
    changes: list[tuple[str, str, str]] = []
    for field_name in LOAN_ACCOUNT_AUDIT_FIELDS:
        old_raw = before.get(field_name)
        new_raw = after.get(field_name)
        old_cmp = "" if old_raw is None else str(old_raw).strip()
        new_cmp = "" if new_raw is None else str(new_raw).strip()
        if field_name in {"issued_amount", "outstanding_balance", "installment_amount", "repayment_progress"}:
            old_cmp = str(old_raw) if old_raw is not None else ""
            new_cmp = str(new_raw) if new_raw is not None else ""
        if old_cmp != new_cmp:
            changes.append(
                (
                    field_name,
                    _format_loan_field(field_name, old_raw),
                    _format_loan_field(field_name, new_raw),
                )
            )
    return changes


def validate_loan_account_form(
    data,
    current: sqlite3.Row | None = None,
) -> tuple[dict | None, str | None]:
    snapshot = loan_snapshot_from_form(data)

    if snapshot["loan_lifecycle_status"] not in LOAN_LIFECYCLE_STATUSES:
        return None, "Select a valid loan lifecycle status."

    if snapshot["repayment_frequency"] and snapshot["repayment_frequency"] not in REPAYMENT_FREQUENCIES:
        return None, "Select a valid repayment frequency."

    if snapshot["repayment_risk_level"] not in REPAYMENT_RISK_LEVELS:
        return None, "Select a valid repayment risk level."

    if len(snapshot["loan_account_number"]) > MAX_LOAN_ACCOUNT_NUMBER_LENGTH:
        return None, f"Loan account number must be {MAX_LOAN_ACCOUNT_NUMBER_LENGTH} characters or fewer."

    if len(snapshot["collections_notes"]) > MAX_COLLECTIONS_NOTES_LENGTH:
        return None, f"Collections notes must be {MAX_COLLECTIONS_NOTES_LENGTH} characters or fewer."

    if len(snapshot["missed_payment_observations"]) > MAX_MISSED_PAYMENT_OBSERVATIONS_LENGTH:
        return (
            None,
            f"Missed payment observations must be {MAX_MISSED_PAYMENT_OBSERVATIONS_LENGTH} characters or fewer.",
        )

    if snapshot["loan_lifecycle_status"] in SERVICING_LOAN_LIFECYCLE_STATUSES:
        if snapshot["issued_amount"] is None or snapshot["issued_amount"] <= 0:
            return None, "Issued amount is required for active loan accounts."
        if snapshot["outstanding_balance"] is None:
            return None, "Outstanding balance is required for active loan accounts."

    if snapshot["loan_lifecycle_status"] in LOAN_STATUSES_REQUIRING_COLLECTIONS_NOTE:
        if not snapshot["collections_notes"] and not snapshot["missed_payment_observations"]:
            return (
                None,
                "Provide collections notes or missed-payment observations for overdue or distressed loans.",
            )

    if current is not None:
        before = loan_snapshot_from_row(current)
        activating = (
            before["loan_lifecycle_status"] == DEFAULT_LOAN_LIFECYCLE_STATUS
            and snapshot["loan_lifecycle_status"] in ACTIVE_LOAN_LIFECYCLE_STATUSES
        )
        if activating:
            underwriting_status = current["underwriting_status"] or ""
            if underwriting_status not in UNDERWRITING_STATUSES_ELIGIBLE_FOR_LOAN_ACTIVATION:
                return (
                    None,
                    "Loan activation is recommended only after financing approval "
                    "(approved or conditionally approved).",
                )
            if not snapshot["loan_account_number"]:
                snapshot["loan_account_number"] = generate_loan_account_number(current["id"])
            if snapshot["issued_amount"] is None and current["loan_amount"]:
                snapshot["issued_amount"] = float(current["loan_amount"])
                snapshot["outstanding_balance"] = snapshot["outstanding_balance"] or snapshot["issued_amount"]
                snapshot["repayment_progress"] = compute_repayment_progress(
                    snapshot["issued_amount"],
                    snapshot["outstanding_balance"],
                )

        if before == snapshot:
            return None, "No loan account changes were detected."

    snapshot["repayment_progress"] = compute_repayment_progress(
        snapshot["issued_amount"],
        snapshot["outstanding_balance"],
    )
    return snapshot, None


def _application_value(application: sqlite3.Row | dict, key: str, default=None):
    if hasattr(application, "keys") and key not in application.keys():
        return default
    try:
        value = application[key]
    except (KeyError, TypeError):
        return default
    return default if value is None else value


def delinquency_context(application: sqlite3.Row | dict) -> dict:
    lifecycle = _application_value(application, "loan_lifecycle_status", DEFAULT_LOAN_LIFECYCLE_STATUS)
    outstanding = _application_value(application, "outstanding_balance")
    due_date_raw = (_application_value(application, "due_date", "") or "").strip()

    if lifecycle in TERMINAL_LOAN_LIFECYCLE_STATUSES or lifecycle == DEFAULT_LOAN_LIFECYCLE_STATUS:
        return {
            "is_delinquent": False,
            "days_overdue": 0,
            "show_collections_banner": False,
            "delinquency_label": "",
        }

    days_overdue = 0
    if due_date_raw and outstanding is not None and float(outstanding) > 0:
        try:
            due_day = date.fromisoformat(due_date_raw[:10])
            days_overdue = max(0, (date.today() - due_day).days)
        except ValueError:
            days_overdue = 0

    is_delinquent = lifecycle == "overdue" or days_overdue > 0
    show_banner = is_delinquent and lifecycle in ACTIVE_LOAN_LIFECYCLE_STATUSES.union({"defaulted"})
    label = ""
    if is_delinquent and days_overdue > 0:
        label = f"{days_overdue} day{'s' if days_overdue != 1 else ''} past due"
    elif lifecycle == "overdue":
        label = "Marked overdue"

    return {
        "is_delinquent": is_delinquent,
        "days_overdue": days_overdue,
        "show_collections_banner": show_banner,
        "delinquency_label": label,
    }


def loan_servicing_summary(application: sqlite3.Row | dict) -> str:
    lifecycle = application["loan_lifecycle_status"] or DEFAULT_LOAN_LIFECYCLE_STATUS
    label = LOAN_LIFECYCLE_STATUS_LABELS.get(lifecycle, lifecycle)
    parts = [label]
    if application["loan_account_number"]:
        parts.append(application["loan_account_number"])
    if application["outstanding_balance"] is not None and lifecycle in SERVICING_LOAN_LIFECYCLE_STATUSES:
        parts.append(f"Outstanding: {application['outstanding_balance']}")
    if application["repayment_progress"] is not None and lifecycle in SERVICING_LOAN_LIFECYCLE_STATUSES:
        parts.append(f"{application['repayment_progress']}% repaid")
    risk = application["repayment_risk_level"] or "current"
    if risk != "current":
        parts.append(REPAYMENT_RISK_LABELS.get(risk, risk))
    return " — ".join(parts)


def loan_collections_attention(application: sqlite3.Row | dict) -> bool:
    if hasattr(application, "keys") and "loan_lifecycle_status" not in application.keys():
        return False
    delinquency = delinquency_context(application)
    risk = _application_value(application, "repayment_risk_level", "current") or "current"
    lifecycle = _application_value(application, "loan_lifecycle_status", DEFAULT_LOAN_LIFECYCLE_STATUS)
    return delinquency["show_collections_banner"] or risk in {"elevated", "critical"} or lifecycle == "defaulted"


def group_loan_account_history(rows: list) -> list[dict]:
    batches: list[dict] = []
    index_by_batch: dict[str, int] = {}

    for row in rows:
        batch_id = row["batch_id"]
        status_label = LOAN_LIFECYCLE_STATUS_LABELS.get(
            row["loan_lifecycle_status"],
            row["loan_lifecycle_status"],
        )
        entry = {
            "loan_lifecycle_status": row["loan_lifecycle_status"],
            "status_label": status_label,
            "loan_account_number": row["loan_account_number"],
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
                    "status_label": status_label,
                    "loan_account_number": row["loan_account_number"],
                    "outstanding_balance": row["outstanding_balance"],
                    "repayment_progress": row["repayment_progress"],
                    "is_critical": entry["is_critical"],
                }
            )
    return batches


def persist_loan_account_update(
    application_id: int,
    application: sqlite3.Row,
    snapshot: dict,
    actor: str,
    *,
    context_notes: str = "",
) -> None:
    before = loan_snapshot_from_row(application)
    after = dict(snapshot)
    changes = diff_loan_snapshots(before, after)
    if not changes:
        return

    batch_id = secrets.token_hex(8)
    is_critical = 1 if after["loan_lifecycle_status"] in LOAN_LIFECYCLE_CRITICAL_STATUSES else 0

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE applications
            SET
                loan_lifecycle_status = ?,
                loan_account_number = ?,
                issued_amount = ?,
                outstanding_balance = ?,
                repayment_progress = ?,
                issue_date = ?,
                due_date = ?,
                installment_amount = ?,
                repayment_frequency = ?,
                collections_notes = ?,
                missed_payment_observations = ?,
                repayment_risk_level = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                after["loan_lifecycle_status"],
                after["loan_account_number"],
                after["issued_amount"],
                after["outstanding_balance"],
                after["repayment_progress"],
                after["issue_date"],
                after["due_date"],
                after["installment_amount"],
                after["repayment_frequency"],
                after["collections_notes"],
                after["missed_payment_observations"],
                after["repayment_risk_level"],
                application_id,
            ),
        )

        insert_loan_account_history_record(
            cursor,
            application_id=application_id,
            batch_id=batch_id,
            snapshot=after,
            actor=actor,
            context_notes=context_notes[:MAX_LOAN_ACCOUNT_CONTEXT_LENGTH],
            is_critical=is_critical,
        )

        previous_state = json.dumps(before, sort_keys=True, default=str)
        new_state = json.dumps(after, sort_keys=True, default=str)
        for field_name, old_value, new_value in changes:
            field_critical = (
                1
                if field_name == "loan_lifecycle_status"
                and after["loan_lifecycle_status"] in LOAN_LIFECYCLE_CRITICAL_STATUSES
                else 0
            )
            field_action = LOAN_FIELD_ACTION_TYPES.get(field_name, "loan_account_update")
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
                    context_notes[:MAX_LOAN_ACCOUNT_CONTEXT_LENGTH],
                    field_critical,
                    None,
                ),
            )

        conn.commit()
    except Exception as exc:
        conn.rollback()
        log_workflow_failure(
            "Loan account persistence failed",
            application_id=application_id,
            actor=actor,
            error=str(exc),
        )
        raise
    finally:
        conn.close()

    if is_critical:
        log_governance_event(
            "Critical loan lifecycle event recorded",
            critical=True,
            application_id=application_id,
            actor=actor,
            loan_lifecycle_status=after["loan_lifecycle_status"],
            batch_id=batch_id,
        )


def validate_repayment_form(
    data,
    application: sqlite3.Row,
) -> tuple[dict | None, str | None]:
    lifecycle = application["loan_lifecycle_status"] or DEFAULT_LOAN_LIFECYCLE_STATUS
    if lifecycle not in SERVICING_LOAN_LIFECYCLE_STATUSES:
        return None, "Repayments can only be recorded for active, repaying, overdue, or defaulted loans."

    payment_date = (data.get("payment_date") or "").strip()
    if not payment_date:
        payment_date = date.today().isoformat()
    else:
        try:
            date.fromisoformat(payment_date[:10])
        except ValueError:
            return None, "Enter a valid payment date (YYYY-MM-DD)."

    amount = _parse_optional_float(data.get("payment_amount"))
    if amount is None or amount <= 0:
        return None, "Payment amount must be greater than zero."

    outstanding = application["outstanding_balance"]
    if outstanding is None:
        return None, "Set an outstanding balance on the loan account before recording repayments."

    if amount > float(outstanding):
        return None, "Payment amount cannot exceed the current outstanding balance."

    notes = (data.get("repayment_notes") or "").strip()
    if len(notes) > MAX_REPAYMENT_NOTES_LENGTH:
        return None, f"Repayment notes must be {MAX_REPAYMENT_NOTES_LENGTH} characters or fewer."

    return {
        "payment_date": payment_date[:10],
        "payment_amount": amount,
        "repayment_notes": notes,
    }, None


def persist_repayment(
    application_id: int,
    application: sqlite3.Row,
    repayment: dict,
    actor: str,
) -> dict:
    batch_id = secrets.token_hex(8)
    balance_before = float(application["outstanding_balance"] or 0)
    balance_after = round(max(0.0, balance_before - repayment["payment_amount"]), 2)
    issued = application["issued_amount"]
    progress = compute_repayment_progress(issued, balance_after)

    lifecycle = application["loan_lifecycle_status"] or DEFAULT_LOAN_LIFECYCLE_STATUS
    new_lifecycle = lifecycle
    if balance_after == 0:
        new_lifecycle = "completed"
    elif lifecycle == "active":
        new_lifecycle = "repaying"

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        insert_repayment_record(
            cursor,
            application_id=application_id,
            batch_id=batch_id,
            payment_date=repayment["payment_date"],
            payment_amount=repayment["payment_amount"],
            balance_before=balance_before,
            balance_after=balance_after,
            repayment_notes=repayment["repayment_notes"],
            actor=actor,
        )

        cursor.execute(
            """
            UPDATE applications
            SET
                outstanding_balance = ?,
                repayment_progress = ?,
                loan_lifecycle_status = ?,
                last_payment_at = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                balance_after,
                progress,
                new_lifecycle,
                repayment["payment_date"],
                application_id,
            ),
        )

        summary = (
            f"Payment {repayment['payment_amount']} on {repayment['payment_date']}; "
            f"balance {balance_before} → {balance_after}"
        )
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
                "repayment_recorded",
                "outstanding_balance",
                str(balance_before),
                str(balance_after),
                str(balance_before),
                str(balance_after),
                actor,
                repayment["repayment_notes"] or summary,
                0,
                None,
            ),
        )

        conn.commit()
    except Exception as exc:
        conn.rollback()
        log_workflow_failure(
            "Repayment persistence failed",
            application_id=application_id,
            actor=actor,
            error=str(exc),
        )
        raise
    finally:
        conn.close()

    return {
        "balance_after": balance_after,
        "repayment_progress": progress,
        "loan_lifecycle_status": new_lifecycle,
        "paid_in_full": balance_after == 0,
    }
