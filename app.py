import base64
import csv
import hmac
import io
import json
import os
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv()
import re
import secrets
import sqlite3
from functools import wraps

from flask import Flask, Response, flash, g, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-secret-key-change-me")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_PRODUCTS = {"MarginPro", "HustleBoost", "QuickBridge"}

DATABASE_PATH = os.getenv("DATABASE_PATH", "database.db")

APPLICATION_STATUSES = (
    "New applicant",
    "Collection of documentation",
    "Approval",
    "Management approval",
    "Signing agreement",
    "Final review",
    "Pending payments",
    "Loan issued",
    "Rejected",
)

KPI_PENDING_STATUSES = (
    "New applicant",
    "Collection of documentation",
    "Approval",
    "Management approval",
    "Signing agreement",
    "Final review",
)

KPI_APPROVED_STATUSES = ("Pending payments", "Loan issued")
KPI_REJECTED_STATUS = "Rejected"
KPI_HIGH_RISK_LEVELS = ("High", "Critical")

KPI_ACTIVE_PIPELINE_STATUSES = KPI_PENDING_STATUSES

KPI_CLIENT_ACTION_SUB_STATUSES = (
    "Client thinking",
    "Client to submit documentation",
    "Additional documentation",
    "Branch visit arranged",
    "Waiting for Other",
)

KPI_OPS_REVIEW_SUB_STATUS = "Margin to act"

ADMIN_FILTER_PRESETS = {
    "pipeline": "Active pipeline",
    "approved": "Approved applications",
    "rejected": "Rejected applications",
    "high_risk": "High-risk applications",
    "awaiting_client": "Awaiting client action",
    "ops_review": "Pending operational review",
}

ADMIN_PAGE_SIZE = 15
ADMIN_SEARCH_MAX_LENGTH = 100
OVERVIEW_LIST_LIMIT = 8
OVERVIEW_OFFICER_LIMIT = 6
ANALYTICS_OFFICER_LIMIT = 10
ANALYTICS_MAX_TREND_POINTS = 90

ANALYTICS_TIME_RANGES = {
    "today": "Today",
    "7d": "Last 7 days",
    "30d": "Last 30 days",
    "90d": "Last 90 days",
    "all": "All time",
}

DEFAULT_ANALYTICS_RANGE = "30d"

ADMIN_LIST_FILTER_KEYS = (
    "status",
    "sub_status",
    "risk_level",
    "flagged_fraud",
    "assigned_officer",
    "q",
    "preset",
)

APPLICATION_SUB_STATUSES = (
    "Additional documentation",
    "Client thinking",
    "Client to submit documentation",
    "Branch visit arranged",
    "Waiting for Other",
    "Margin to act",
)

DEFAULT_APPLICATION_STATUS = APPLICATION_STATUSES[0]
DEFAULT_RISK_LEVEL = "Unassigned"

APPLICATION_RISK_LEVELS = (
    "Unassigned",
    "Low",
    "Medium",
    "High",
    "Critical",
)

MAX_APPROVAL_NOTES_LENGTH = 5000
MAX_ASSIGNED_OFFICER_LENGTH = 150

WORKFLOW_STATUS_GROUPS = (
    ("Intake & documentation", ("New applicant", "Collection of documentation")),
    ("Approval", ("Approval", "Management approval", "Signing agreement", "Final review")),
    ("Funding", ("Pending payments", "Loan issued")),
    ("Closed", (KPI_REJECTED_STATUS,)),
)

WORKFLOW_SUB_STATUS_GROUPS = (
    ("Client action", KPI_CLIENT_ACTION_SUB_STATUSES),
    ("Operations", (KPI_OPS_REVIEW_SUB_STATUS, "Additional documentation", "Branch visit arranged", "Waiting for Other")),
)

OFFICER_NAME_PATTERN = re.compile(r"^[\w\s.'\-]{0,150}$", re.UNICODE)

WORKFLOW_HISTORY_LIMIT = 100
MAX_AUDIT_CONTEXT_LENGTH = 1000
PUBLIC_INTAKE_ACTOR = "Public intake"

WORKFLOW_AUDIT_FIELDS = (
    "status",
    "sub_status",
    "risk_level",
    "assigned_officer",
    "flagged_fraud",
    "approval_notes",
)

WORKFLOW_FIELD_ACTION_TYPES = {
    "status": "status_change",
    "sub_status": "sub_status_change",
    "risk_level": "risk_level_change",
    "flagged_fraud": "fraud_flag_change",
    "assigned_officer": "officer_assignment",
    "approval_notes": "notes_update",
}

QUICK_ACTION_AUDIT_TYPES = {
    "advance_status": "quick_action_advance",
    "margin_to_act": "quick_action_margin_to_act",
    "clear_sub_status": "quick_action_clear_sub_status",
    "mark_high_risk": "quick_action_high_risk",
    "clear_fraud_flag": "quick_action_clear_fraud",
}

QUICK_ACTIONS_REQUIRING_AUDIT_NOTE = frozenset({"mark_high_risk", "clear_fraud_flag"})

SENSITIVE_AUDIT_STATUSES = frozenset({"Management approval", "Rejected", "Loan issued"})

REPORT_EXPORT_MAX_ROWS = 10000

REPORT_EXPORT_TYPES = frozenset(
    {
        "operational",
        "pipeline",
        "outcomes",
        "risk",
        "fraud",
        "officers",
        "backlog",
    }
)

APPLICATION_EXPORT_COLUMNS = (
    ("id", "id"),
    ("business_name", "business_name"),
    ("owner_name", "owner_name"),
    ("email", "email"),
    ("revenue", "revenue"),
    ("product", "product"),
    ("status", "status"),
    ("sub_status", "sub_status"),
    ("risk_level", "risk_level"),
    ("flagged_fraud", "flagged_fraud"),
    ("assigned_officer", "assigned_officer"),
    ("created_at", "created_at"),
    ("updated_at", "updated_at"),
)

AUDIT_EXPORT_COLUMNS = (
    ("id", "id"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("batch_id", "batch_id"),
    ("action_type", "action_type"),
    ("field_name", "field_name"),
    ("old_value", "old_value"),
    ("new_value", "new_value"),
    ("actor", "actor"),
    ("context_notes", "context_notes"),
    ("is_critical", "is_critical"),
    ("transition_warning", "transition_warning"),
    ("created_at", "created_at"),
)

# ALTER TABLE only allows constant defaults; timestamps are backfilled after add.
APPLICATIONS_SCHEMA_COLUMNS = (
    ("status", "TEXT NOT NULL DEFAULT 'New applicant'"),
    ("sub_status", "TEXT"),
    ("created_at", "TEXT"),
    ("updated_at", "TEXT"),
    ("risk_level", "TEXT NOT NULL DEFAULT 'Unassigned'"),
    ("approval_notes", "TEXT NOT NULL DEFAULT ''"),
    ("assigned_officer", "TEXT NOT NULL DEFAULT ''"),
    ("phone_number", "TEXT NOT NULL DEFAULT ''"),
    ("business_type", "TEXT NOT NULL DEFAULT ''"),
    ("date_of_birth", "TEXT"),
    ("gender", "TEXT NOT NULL DEFAULT ''"),
    ("flagged_fraud", "INTEGER NOT NULL DEFAULT 0"),
    ("loan_amount", "REAL"),
)


def _is_development() -> bool:
    env_value = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    return env_value in {"dev", "development", "local"}


def _get_bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _ensure_session_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _validate_csrf(form_token: str) -> bool:
    session_token = session.get("csrf_token")
    if not session_token or not form_token:
        return False
    return hmac.compare_digest(session_token, form_token)


def _is_valid_application_form(data) -> bool:
    business_name = (data.get("business_name") or "").strip()
    owner_name = (data.get("owner_name") or "").strip()
    email = (data.get("email") or "").strip()
    product = (data.get("product") or "").strip()
    revenue_raw = (data.get("revenue") or "").strip()

    if not business_name or len(business_name) > 150:
        return False
    if not owner_name or len(owner_name) > 150:
        return False
    if not email or len(email) > 254 or not EMAIL_PATTERN.match(email):
        return False
    if product not in ALLOWED_PRODUCTS:
        return False

    try:
        revenue = float(revenue_raw)
    except ValueError:
        return False

    if revenue <= 0 or revenue > 1_000_000_000:
        return False

    return True


def _parse_basic_auth_credentials(auth_header: str | None) -> tuple[str, str] | None:
    if not auth_header or not auth_header.startswith("Basic "):
        return None

    try:
        encoded_credentials = auth_header.split(" ", 1)[1]
        decoded = base64.b64decode(encoded_credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None


def _check_admin_auth(auth_header: str | None) -> bool:
    credentials = _parse_basic_auth_credentials(auth_header)
    if not credentials:
        return False

    expected_username = os.getenv("ADMIN_USERNAME")
    expected_password = os.getenv("ADMIN_PASSWORD")
    if not expected_username or not expected_password:
        return False

    username, password = credentials
    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(password, expected_password)


def _get_request_actor() -> str:
    configured = os.getenv("ADMIN_USERNAME")
    credentials = _parse_basic_auth_credentials(request.headers.get("Authorization"))
    if credentials:
        username, _password = credentials
        if configured and hmac.compare_digest(username, configured):
            return username
        return username
    return configured or "admin"


def require_admin_auth(route_fn):
    @wraps(route_fn)
    def wrapper(*args, **kwargs):
        if not (os.getenv("ADMIN_USERNAME") and os.getenv("ADMIN_PASSWORD")):
            return Response("Admin credentials are not configured.", status=503)

        if not _check_admin_auth(request.headers.get("Authorization")):
            return Response(
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="Admin Dashboard"'},
            )

        g.admin_actor = _get_request_actor()
        return route_fn(*args, **kwargs)

    return wrapper

def _get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _applications_column_names(cursor) -> set[str]:
    cursor.execute("PRAGMA table_info(applications)")
    return {row[1] for row in cursor.fetchall()}


def _migrate_applications_table(cursor) -> None:
    existing = _applications_column_names(cursor)
    if not existing:
        return

    for column_name, column_def in APPLICATIONS_SCHEMA_COLUMNS:
        if column_name not in existing:
            cursor.execute(f"ALTER TABLE applications ADD COLUMN {column_name} {column_def}")

    cursor.execute(
        """
        UPDATE applications
        SET created_at = datetime('now')
        WHERE created_at IS NULL OR created_at = ''
        """
    )
    cursor.execute(
        """
        UPDATE applications
        SET updated_at = datetime('now')
        WHERE updated_at IS NULL OR updated_at = ''
        """
    )
    cursor.execute(
        """
        UPDATE applications
        SET status = ?
        WHERE status IS NULL OR status = ''
        """,
        (DEFAULT_APPLICATION_STATUS,),
    )
    cursor.execute(
        """
        UPDATE applications
        SET risk_level = ?
        WHERE risk_level IS NULL OR risk_level = ''
        """,
        (DEFAULT_RISK_LEVEL,),
    )
    cursor.execute(
        """
        UPDATE applications
        SET flagged_fraud = 0
        WHERE flagged_fraud IS NULL
        """
    )


def init_db():
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            email TEXT NOT NULL,
            revenue REAL NOT NULL,
            product TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'New applicant',
            sub_status TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            risk_level TEXT NOT NULL DEFAULT 'Unassigned',
            approval_notes TEXT NOT NULL DEFAULT '',
            assigned_officer TEXT NOT NULL DEFAULT '',
            phone_number TEXT NOT NULL DEFAULT '',
            business_type TEXT NOT NULL DEFAULT '',
            date_of_birth TEXT,
            gender TEXT NOT NULL DEFAULT '',
            flagged_fraud INTEGER NOT NULL DEFAULT 0,
            loan_amount REAL
        )
        """
    )

    _migrate_applications_table(cursor)
    _init_workflow_history_table(cursor)
    _init_officers_table(cursor)
    _seed_officers_table(cursor)

    conn.commit()
    conn.close()


def _init_workflow_history_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            previous_state TEXT NOT NULL,
            new_state TEXT NOT NULL,
            actor TEXT NOT NULL,
            context_notes TEXT NOT NULL DEFAULT '',
            is_critical INTEGER NOT NULL DEFAULT 0,
            transition_warning TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_history_application
        ON workflow_history (application_id, created_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_workflow_history_batch
        ON workflow_history (batch_id)
        """
    )


def _init_officers_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS officers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _seed_officers_table(cursor) -> None:
    cursor.execute(
        """
        SELECT DISTINCT assigned_officer AS name
        FROM applications
        WHERE assigned_officer IS NOT NULL AND TRIM(assigned_officer) != ''
        """
    )
    for row in cursor.fetchall():
        cursor.execute(
            "INSERT OR IGNORE INTO officers (name) VALUES (?)",
            (row["name"],),
        )


def _ensure_officer_registered(cursor, officer_name: str) -> None:
    if not officer_name:
        return
    cursor.execute("INSERT OR IGNORE INTO officers (name) VALUES (?)", (officer_name,))


def _fetch_registered_officers(cursor) -> list[str]:
    cursor.execute(
        """
        SELECT name FROM officers
        WHERE active = 1
        ORDER BY name COLLATE NOCASE ASC
        """
    )
    registered = [row["name"] for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT DISTINCT assigned_officer AS name
        FROM applications
        WHERE assigned_officer IS NOT NULL AND TRIM(assigned_officer) != ''
        ORDER BY assigned_officer COLLATE NOCASE ASC
        """
    )
    seen = {name.casefold() for name in registered}
    merged = list(registered)
    for row in cursor.fetchall():
        name = row["name"]
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            merged.append(name)
    return merged


def _resolve_officer_name(raw_officer: str, known_officers: list[str]) -> str:
    normalized = _normalize_officer_name(raw_officer)
    if not normalized:
        return ""
    for known in known_officers:
        if known.casefold() == normalized.casefold():
            return known
    return normalized


def _workflow_snapshot_from_row(row: sqlite3.Row | dict) -> dict:
    return {
        "status": row["status"],
        "sub_status": row["sub_status"],
        "risk_level": row["risk_level"],
        "assigned_officer": row["assigned_officer"] or "",
        "flagged_fraud": int(row["flagged_fraud"] or 0),
        "approval_notes": row["approval_notes"] or "",
    }


def _workflow_snapshot_from_workflow(workflow: dict) -> dict:
    return {
        "status": workflow["status"],
        "sub_status": workflow["sub_status"],
        "risk_level": workflow["risk_level"],
        "assigned_officer": workflow["assigned_officer"],
        "flagged_fraud": workflow["flagged_fraud"],
        "approval_notes": workflow["approval_notes"],
    }


def _workflow_snapshot_json(snapshot: dict) -> str:
    payload = {
        **snapshot,
        "sub_status": snapshot["sub_status"] or "",
    }
    return json.dumps(payload, sort_keys=True)


def _format_audit_field_value(field_name: str, value) -> str:
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


def _diff_workflow_snapshots(before: dict, after: dict) -> list[tuple[str, str, str]]:
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
                    _format_audit_field_value(field_name, old_raw),
                    _format_audit_field_value(field_name, new_raw),
                )
            )
    return changes


def _workflow_change_is_critical(field_name: str, old_value: str, new_value: str) -> bool:
    if field_name == "flagged_fraud":
        return new_value == "Flagged"
    if field_name == "risk_level" and new_value in {"High", "Critical"}:
        return new_value != old_value
    if field_name == "status" and new_value in SENSITIVE_AUDIT_STATUSES.union({KPI_REJECTED_STATUS}):
        return new_value != old_value
    if field_name == "sub_status" and new_value == KPI_OPS_REVIEW_SUB_STATUS:
        return new_value != old_value
    return False


def _is_risky_status_transition_warning(current_status: str, next_status: str) -> str | None:
    if current_status == next_status:
        return None

    if not _is_allowed_status_transition(current_status, next_status):
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


def _requires_audit_context(
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
        if _is_risky_status_transition_warning(before["status"], after["status"]):
            return True

    if after["risk_level"] == "Critical" and after["risk_level"] != before["risk_level"]:
        return True

    return False


def _normalize_audit_context(raw_value: str) -> str:
    return (raw_value or "").strip()[:MAX_AUDIT_CONTEXT_LENGTH]


def _validate_audit_context(raw_value: str, required: bool) -> tuple[str, str | None]:
    notes = _normalize_audit_context(raw_value)
    if required and not notes:
        return "", "An operational note is required for this sensitive workflow action."
    if len((raw_value or "").strip()) > MAX_AUDIT_CONTEXT_LENGTH:
        return "", f"Operational note must be {MAX_AUDIT_CONTEXT_LENGTH} characters or fewer."
    return notes, None


def _history_event_summary(field_name: str, old_value: str, new_value: str) -> str:
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


def _insert_workflow_history_entries(
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

    previous_state = _workflow_snapshot_json(before)
    new_state = _workflow_snapshot_json(after)

    for field_name, old_value, new_value in changes:
        field_action = WORKFLOW_FIELD_ACTION_TYPES.get(field_name, action_type)
        is_critical = 1 if _workflow_change_is_critical(field_name, old_value, new_value) else 0
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


def _persist_workflow_update(
    application_id: int,
    application: sqlite3.Row,
    workflow: dict,
    actor: str,
    *,
    quick_action: str | None = None,
    context_notes: str = "",
    transition_warning: str | None = None,
) -> None:
    before = _workflow_snapshot_from_row(application)
    after = _workflow_snapshot_from_workflow(workflow)
    changes = _diff_workflow_snapshots(before, after)
    if not changes:
        return

    conn = _get_db_connection()
    cursor = conn.cursor()
    if workflow["assigned_officer"]:
        _ensure_officer_registered(cursor, workflow["assigned_officer"])
    batch_id = secrets.token_hex(8)
    action_type = QUICK_ACTION_AUDIT_TYPES.get(quick_action or "", "workflow_update")

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

    _insert_workflow_history_entries(
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
    conn.close()


def _log_application_created(cursor, application_id: int) -> None:
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
    _insert_workflow_history_entries(
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


def _fetch_workflow_history_rows(cursor, application_id: int, limit: int = WORKFLOW_HISTORY_LIMIT) -> list:
    cursor.execute(
        """
        SELECT
            id,
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
        FROM workflow_history
        WHERE application_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (application_id, limit),
    )
    return cursor.fetchall()


def _group_workflow_history_batches(rows: list) -> list[dict]:
    batches: list[dict] = []
    index_by_batch: dict[str, int] = {}

    for row in rows:
        batch_id = row["batch_id"]
        event = {
            "field_name": row["field_name"],
            "summary": _history_event_summary(row["field_name"], row["old_value"], row["new_value"]),
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


def _parse_admin_list_filters(args) -> dict:
    status = (args.get("status") or "").strip()
    if status and status not in APPLICATION_STATUSES:
        status = ""

    sub_status = (args.get("sub_status") or "").strip()
    if sub_status and sub_status not in APPLICATION_SUB_STATUSES:
        sub_status = ""

    risk_level = (args.get("risk_level") or "").strip()
    if risk_level and risk_level not in APPLICATION_RISK_LEVELS:
        risk_level = ""

    flagged_fraud = (args.get("flagged_fraud") or "").strip()
    if flagged_fraud not in {"", "0", "1"}:
        flagged_fraud = ""

    assigned_officer = (args.get("assigned_officer") or "").strip()
    if len(assigned_officer) > MAX_ASSIGNED_OFFICER_LENGTH:
        assigned_officer = assigned_officer[:MAX_ASSIGNED_OFFICER_LENGTH]

    search_query = (args.get("q") or "").strip()
    if len(search_query) > ADMIN_SEARCH_MAX_LENGTH:
        search_query = search_query[:ADMIN_SEARCH_MAX_LENGTH]

    preset = (args.get("preset") or "").strip()
    if preset not in ADMIN_FILTER_PRESETS:
        preset = ""

    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    return {
        "status": status,
        "sub_status": sub_status,
        "risk_level": risk_level,
        "flagged_fraud": flagged_fraud,
        "assigned_officer": assigned_officer,
        "q": search_query,
        "preset": preset,
        "page": page,
    }


def _build_applications_where(filters: dict) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []

    preset = filters.get("preset") or ""
    if preset == "pipeline":
        placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
        clauses.append(f"status IN ({placeholders})")
        params.extend(KPI_ACTIVE_PIPELINE_STATUSES)
    elif preset == "approved":
        placeholders = ", ".join("?" * len(KPI_APPROVED_STATUSES))
        clauses.append(f"status IN ({placeholders})")
        params.extend(KPI_APPROVED_STATUSES)
    elif preset == "rejected":
        clauses.append("status = ?")
        params.append(KPI_REJECTED_STATUS)
    elif preset == "high_risk":
        placeholders = ", ".join("?" * len(KPI_HIGH_RISK_LEVELS))
        clauses.append(f"risk_level IN ({placeholders})")
        params.extend(KPI_HIGH_RISK_LEVELS)
    elif preset == "awaiting_client":
        placeholders = ", ".join("?" * len(KPI_CLIENT_ACTION_SUB_STATUSES))
        clauses.append(f"sub_status IN ({placeholders})")
        params.extend(KPI_CLIENT_ACTION_SUB_STATUSES)
    elif preset == "ops_review":
        pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
        clauses.append(
            f"(sub_status = ? OR (status IN ({pipeline_placeholders}) AND "
            "(assigned_officer IS NULL OR TRIM(assigned_officer) = '')))"
        )
        params.append(KPI_OPS_REVIEW_SUB_STATUS)
        params.extend(KPI_ACTIVE_PIPELINE_STATUSES)

    if filters["status"]:
        clauses.append("status = ?")
        params.append(filters["status"])

    if filters["sub_status"]:
        clauses.append("sub_status = ?")
        params.append(filters["sub_status"])

    if filters["risk_level"]:
        clauses.append("risk_level = ?")
        params.append(filters["risk_level"])

    if filters["flagged_fraud"] in {"0", "1"}:
        clauses.append("flagged_fraud = ?")
        params.append(int(filters["flagged_fraud"]))

    if filters["assigned_officer"]:
        clauses.append("assigned_officer LIKE ?")
        params.append(f"%{filters['assigned_officer']}%")

    if filters["q"]:
        like_term = f"%{filters['q']}%"
        clauses.append(
            "(business_name LIKE ? OR owner_name LIKE ? OR email LIKE ? OR phone_number LIKE ?)"
        )
        params.extend([like_term, like_term, like_term, like_term])

    if clauses:
        return " WHERE " + " AND ".join(clauses), params
    return "", params


def _filters_to_query_params(filters: dict) -> dict:
    return {key: filters[key] for key in ADMIN_LIST_FILTER_KEYS if filters.get(key)}


def _fetch_executive_kpis(cursor) -> dict:
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    approved_placeholders = ", ".join("?" * len(KPI_APPROVED_STATUSES))
    high_risk_placeholders = ", ".join("?" * len(KPI_HIGH_RISK_LEVELS))
    client_placeholders = ", ".join("?" * len(KPI_CLIENT_ACTION_SUB_STATUSES))

    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_applications,
            SUM(CASE WHEN status IN ({pipeline_placeholders}) THEN 1 ELSE 0 END)
                AS active_pipeline,
            SUM(CASE WHEN status IN ({approved_placeholders}) THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN risk_level IN ({high_risk_placeholders}) THEN 1 ELSE 0 END) AS high_risk,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_flagged,
            SUM(
                CASE
                    WHEN sub_status = ?
                        OR (
                            status IN ({pipeline_placeholders})
                            AND (assigned_officer IS NULL OR TRIM(assigned_officer) = '')
                        )
                    THEN 1
                    ELSE 0
                END
            ) AS pending_ops_review,
            SUM(CASE WHEN sub_status IN ({client_placeholders}) THEN 1 ELSE 0 END)
                AS awaiting_client_action
        FROM applications
        """,
        (
            *KPI_ACTIVE_PIPELINE_STATUSES,
            *KPI_APPROVED_STATUSES,
            KPI_REJECTED_STATUS,
            *KPI_HIGH_RISK_LEVELS,
            KPI_OPS_REVIEW_SUB_STATUS,
            *KPI_ACTIVE_PIPELINE_STATUSES,
            *KPI_CLIENT_ACTION_SUB_STATUSES,
        ),
    )
    row = cursor.fetchone()
    return {
        "total_applications": row["total_applications"] or 0,
        "active_pipeline": row["active_pipeline"] or 0,
        "approved": row["approved"] or 0,
        "rejected": row["rejected"] or 0,
        "high_risk": row["high_risk"] or 0,
        "fraud_flagged": row["fraud_flagged"] or 0,
        "pending_ops_review": row["pending_ops_review"] or 0,
        "awaiting_client_action": row["awaiting_client_action"] or 0,
    }


def _fetch_application_kpis(cursor) -> dict:
    executive = _fetch_executive_kpis(cursor)
    return {
        "total_applications": executive["total_applications"],
        "pending_review": executive["active_pipeline"],
        "approved": executive["approved"],
        "rejected": executive["rejected"],
        "high_risk": executive["high_risk"],
        "fraud_flagged": executive["fraud_flagged"],
    }


def _fetch_status_distribution(cursor) -> list[dict]:
    cursor.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM applications
        GROUP BY status
        ORDER BY count DESC, status COLLATE NOCASE ASC
        """
    )
    return [{"label": row["status"], "count": row["count"]} for row in cursor.fetchall()]


def _fetch_risk_distribution(cursor) -> list[dict]:
    cursor.execute(
        """
        SELECT risk_level, COUNT(*) AS count
        FROM applications
        GROUP BY risk_level
        ORDER BY count DESC, risk_level COLLATE NOCASE ASC
        """
    )
    return [{"label": row["risk_level"], "count": row["count"]} for row in cursor.fetchall()]


def _fetch_pipeline_backlog(cursor) -> list[dict]:
    placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT status, COUNT(*) AS count
        FROM applications
        WHERE status IN ({placeholders})
        GROUP BY status
        ORDER BY count DESC
        """,
        KPI_ACTIVE_PIPELINE_STATUSES,
    )
    return [{"label": row["status"], "count": row["count"]} for row in cursor.fetchall()]


def _fetch_officer_workload(cursor, limit: int = OVERVIEW_OFFICER_LIMIT) -> list[dict]:
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            CASE
                WHEN assigned_officer IS NULL OR TRIM(assigned_officer) = ''
                THEN 'Unassigned'
                ELSE assigned_officer
            END AS officer_label,
            COUNT(*) AS total_count,
            SUM(CASE WHEN status IN ({pipeline_placeholders}) THEN 1 ELSE 0 END) AS pipeline_count,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_count
        FROM applications
        GROUP BY officer_label
        ORDER BY pipeline_count DESC, total_count DESC, officer_label COLLATE NOCASE ASC
        LIMIT ?
        """,
        (*KPI_ACTIVE_PIPELINE_STATUSES, limit),
    )
    return [
        {
            "officer": row["officer_label"],
            "total_count": row["total_count"],
            "pipeline_count": row["pipeline_count"],
            "fraud_count": row["fraud_count"],
        }
        for row in cursor.fetchall()
    ]


def _fetch_recent_applications(cursor, limit: int = OVERVIEW_LIST_LIMIT) -> list:
    cursor.execute(
        """
        SELECT
            id,
            business_name,
            owner_name,
            status,
            risk_level,
            created_at
        FROM applications
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()


def _fetch_attention_applications(cursor, limit: int = OVERVIEW_LIST_LIMIT) -> list:
    high_risk_placeholders = ", ".join("?" * len(KPI_HIGH_RISK_LEVELS))
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            id,
            business_name,
            owner_name,
            status,
            sub_status,
            risk_level,
            flagged_fraud,
            assigned_officer,
            updated_at
        FROM applications
        WHERE
            flagged_fraud = 1
            OR risk_level IN ({high_risk_placeholders})
            OR sub_status = ?
            OR (
                status IN ({pipeline_placeholders})
                AND (assigned_officer IS NULL OR TRIM(assigned_officer) = '')
            )
        ORDER BY
            flagged_fraud DESC,
            CASE risk_level
                WHEN 'Critical' THEN 4
                WHEN 'High' THEN 3
                WHEN 'Medium' THEN 2
                WHEN 'Low' THEN 1
                ELSE 0
            END DESC,
            datetime(updated_at) ASC,
            id ASC
        LIMIT ?
        """,
        (
            *KPI_HIGH_RISK_LEVELS,
            KPI_OPS_REVIEW_SUB_STATUS,
            *KPI_ACTIVE_PIPELINE_STATUSES,
            limit,
        ),
    )
    return cursor.fetchall()


def _overview_drilldown_links() -> dict[str, str]:
    return {
        "total_applications": url_for("admin"),
        "active_pipeline": url_for("admin", preset="pipeline"),
        "approved": url_for("admin", preset="approved"),
        "rejected": url_for("admin", preset="rejected"),
        "high_risk": url_for("admin", preset="high_risk"),
        "fraud_flagged": url_for("admin", flagged_fraud="1"),
        "pending_ops_review": url_for("admin", preset="ops_review"),
        "awaiting_client_action": url_for("admin", preset="awaiting_client"),
    }


def _fetch_distinct_officers(cursor) -> list[str]:
    return _fetch_registered_officers(cursor)


def _parse_analytics_range(args) -> str:
    range_key = (args.get("range") or DEFAULT_ANALYTICS_RANGE).strip()
    if range_key not in ANALYTICS_TIME_RANGES:
        return DEFAULT_ANALYTICS_RANGE
    return range_key


def _analytics_datetime_clause(range_key: str, column: str = "created_at") -> tuple[str, list]:
    if range_key == "all":
        return "", []
    if range_key == "today":
        return f" AND date({column}) = date('now')", []
    day_map = {"7d": 7, "30d": 30, "90d": 90}
    days = day_map[range_key]
    return f" AND datetime({column}) >= datetime('now', '-{days} days')", []


def _analytics_range_span_days(range_key: str) -> int | None:
    if range_key == "today":
        return 1
    if range_key == "7d":
        return 7
    if range_key == "30d":
        return 30
    if range_key == "90d":
        return 90
    return None


def _add_distribution_shares(items: list[dict], total: int | None = None) -> list[dict]:
    denominator = total if total is not None else sum(item["count"] for item in items)
    denominator = denominator or 1
    for item in items:
        item["share"] = round((item["count"] / denominator) * 100, 1)
    return items


def _fill_daily_trend(rows: list[dict], range_key: str) -> list[dict]:
    span_days = _analytics_range_span_days(range_key)
    if span_days is None:
        return [{"label": row["label"], "count": row["count"]} for row in rows]

    counts_by_day = {row["label"]: row["count"] for row in rows}
    end_day = date.today()
    start_day = end_day - timedelta(days=span_days - 1)
    filled: list[dict] = []
    current = start_day
    while current <= end_day:
        key = current.isoformat()
        filled.append({"label": key, "count": counts_by_day.get(key, 0)})
        current += timedelta(days=1)
    return filled


def _prepare_trend_chart(points: list[dict]) -> list[dict]:
    if not points:
        return []
    max_count = max(point["count"] for point in points) or 1
    prepared = []
    for point in points:
        label = point["label"]
        if len(label) == 10 and label[4] == "-":
            display_label = label[5:]
        else:
            display_label = label
        prepared.append(
            {
                "label": label,
                "display_label": display_label,
                "count": point["count"],
                "height_pct": round((point["count"] / max_count) * 100, 1),
            }
        )
    return prepared


def _fetch_analytics_period_kpis(cursor, range_key: str) -> dict:
    created_clause, created_params = _analytics_datetime_clause(range_key, "created_at")
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    approved_placeholders = ", ".join("?" * len(KPI_APPROVED_STATUSES))
    high_risk_placeholders = ", ".join("?" * len(KPI_HIGH_RISK_LEVELS))

    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_applications,
            SUM(CASE WHEN status IN ({pipeline_placeholders}) THEN 1 ELSE 0 END) AS active_pipeline,
            SUM(CASE WHEN status IN ({approved_placeholders}) THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN risk_level IN ({high_risk_placeholders}) THEN 1 ELSE 0 END) AS high_risk,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_flagged
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        """,
        (
            *KPI_ACTIVE_PIPELINE_STATUSES,
            *KPI_APPROVED_STATUSES,
            KPI_REJECTED_STATUS,
            *KPI_HIGH_RISK_LEVELS,
            *created_params,
        ),
    )
    row = cursor.fetchone()
    return {
        "total_applications": row["total_applications"] or 0,
        "active_pipeline": row["active_pipeline"] or 0,
        "approved": row["approved"] or 0,
        "rejected": row["rejected"] or 0,
        "high_risk": row["high_risk"] or 0,
        "fraud_flagged": row["fraud_flagged"] or 0,
    }


def _fetch_analytics_intake_trend(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = _analytics_datetime_clause(range_key, "created_at")
    cursor.execute(
        f"""
        SELECT date(created_at) AS day_label, COUNT(*) AS count
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY date(created_at)
        ORDER BY day_label ASC
        LIMIT ?
        """,
        (*created_params, ANALYTICS_MAX_TREND_POINTS),
    )
    rows = [{"label": row["day_label"], "count": row["count"]} for row in cursor.fetchall()]
    return _prepare_trend_chart(_fill_daily_trend(rows, range_key))


def _fetch_analytics_outcome_trend(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = _analytics_datetime_clause(range_key, "created_at")
    approved_placeholders = ", ".join("?" * len(KPI_APPROVED_STATUSES))
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            date(created_at) AS day_label,
            SUM(CASE WHEN status IN ({approved_placeholders}) THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN status IN ({pipeline_placeholders}) THEN 1 ELSE 0 END) AS pipeline
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY date(created_at)
        ORDER BY day_label ASC
        LIMIT ?
        """,
        (
            *KPI_APPROVED_STATUSES,
            KPI_REJECTED_STATUS,
            *KPI_ACTIVE_PIPELINE_STATUSES,
            *created_params,
            ANALYTICS_MAX_TREND_POINTS,
        ),
    )
    return [
        {
            "label": row["day_label"],
            "approved": row["approved"] or 0,
            "rejected": row["rejected"] or 0,
            "pipeline": row["pipeline"] or 0,
        }
        for row in cursor.fetchall()
    ]


def _fetch_analytics_fraud_trend(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = _analytics_datetime_clause(range_key, "created_at")
    cursor.execute(
        f"""
        SELECT date(created_at) AS day_label, COUNT(*) AS count
        FROM applications
        WHERE flagged_fraud = 1
          AND created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY date(created_at)
        ORDER BY day_label ASC
        LIMIT ?
        """,
        (*created_params, ANALYTICS_MAX_TREND_POINTS),
    )
    rows = [{"label": row["day_label"], "count": row["count"]} for row in cursor.fetchall()]
    return _prepare_trend_chart(_fill_daily_trend(rows, range_key))


def _fetch_analytics_distribution(
    cursor,
    range_key: str,
    *,
    group_column: str,
    order_values: tuple[str, ...] | None = None,
) -> list[dict]:
    created_clause, created_params = _analytics_datetime_clause(range_key, "created_at")
    cursor.execute(
        f"""
        SELECT {group_column} AS label, COUNT(*) AS count
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY {group_column}
        ORDER BY count DESC, label COLLATE NOCASE ASC
        """,
        created_params,
    )
    items = [{"label": row["label"] or "Unknown", "count": row["count"]} for row in cursor.fetchall()]
    if order_values:
        order_index = {value: index for index, value in enumerate(order_values)}
        items.sort(key=lambda item: (order_index.get(item["label"], len(order_values)), -item["count"]))
    return _add_distribution_shares(items)


def _fetch_analytics_pipeline_distribution(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = _analytics_datetime_clause(range_key, "created_at")
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT status AS label, COUNT(*) AS count
        FROM applications
        WHERE status IN ({pipeline_placeholders})
          AND created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY status
        ORDER BY count DESC
        """,
        (*KPI_ACTIVE_PIPELINE_STATUSES, *created_params),
    )
    return _add_distribution_shares([{"label": row["label"], "count": row["count"]} for row in cursor.fetchall()])


def _fetch_analytics_officer_workload(cursor, range_key: str) -> list[dict]:
    created_clause, created_params = _analytics_datetime_clause(range_key, "created_at")
    pipeline_placeholders = ", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))
    cursor.execute(
        f"""
        SELECT
            CASE
                WHEN assigned_officer IS NULL OR TRIM(assigned_officer) = ''
                THEN 'Unassigned'
                ELSE assigned_officer
            END AS officer_label,
            COUNT(*) AS total_count,
            SUM(CASE WHEN status IN ({pipeline_placeholders}) THEN 1 ELSE 0 END) AS pipeline_count,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_count
        FROM applications
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        GROUP BY officer_label
        ORDER BY pipeline_count DESC, total_count DESC, officer_label COLLATE NOCASE ASC
        LIMIT ?
        """,
        (*KPI_ACTIVE_PIPELINE_STATUSES, *created_params, ANALYTICS_OFFICER_LIMIT),
    )
    rows = [
        {
            "officer": row["officer_label"],
            "total_count": row["total_count"],
            "pipeline_count": row["pipeline_count"],
            "fraud_count": row["fraud_count"],
        }
        for row in cursor.fetchall()
    ]
    if not rows:
        return rows
    max_pipeline = max(row["pipeline_count"] for row in rows) or 1
    for row in rows:
        row["load_share"] = round((row["pipeline_count"] / max_pipeline) * 100, 1)
    return rows


def _fetch_analytics_backlog_snapshot(cursor) -> dict:
    pipeline_backlog = _fetch_pipeline_backlog(cursor)
    pipeline_total = sum(item["count"] for item in pipeline_backlog)
    bottleneck = pipeline_backlog[0] if pipeline_backlog else None
    return {
        "pipeline_backlog": _add_distribution_shares(pipeline_backlog, pipeline_total),
        "pipeline_total": pipeline_total,
        "bottleneck_stage": bottleneck["label"] if bottleneck else None,
        "bottleneck_count": bottleneck["count"] if bottleneck else 0,
    }


def _fetch_analytics_activity_summary(cursor, range_key: str) -> dict:
    updated_clause, updated_params = _analytics_datetime_clause(range_key, "created_at")
    cursor.execute(
        f"""
        SELECT COUNT(DISTINCT batch_id) AS updates_in_period
        FROM workflow_history
        WHERE created_at IS NOT NULL AND created_at != ''{updated_clause}
        """,
        updated_params,
    )
    updates_in_period = cursor.fetchone()["updates_in_period"] or 0
    return {"updates_in_period": updates_in_period}


def _analytics_insights(
    period_kpis: dict,
    backlog: dict,
    officer_workload: list[dict],
    pipeline_distribution: list[dict],
) -> list[str]:
    insights: list[str] = []
    if backlog["bottleneck_stage"] and backlog["bottleneck_count"]:
        insights.append(
            f"Largest pipeline bottleneck: {backlog['bottleneck_stage']} "
            f"({backlog['bottleneck_count']} cases)."
        )
    if officer_workload:
        top = officer_workload[0]
        if top["officer"] != "Unassigned" and top["pipeline_count"] > 0:
            insights.append(
                f"Highest active pipeline load: {top['officer']} ({top['pipeline_count']} cases)."
            )
        unassigned = next((row for row in officer_workload if row["officer"] == "Unassigned"), None)
        if unassigned and unassigned["pipeline_count"] > 0:
            insights.append(
                f"{unassigned['pipeline_count']} pipeline cases remain unassigned to an officer."
            )
    if period_kpis["fraud_flagged"]:
        insights.append(
            f"{period_kpis['fraud_flagged']} applications flagged for fraud in this period."
        )
    if period_kpis["high_risk"]:
        insights.append(
            f"{period_kpis['high_risk']} high-risk or critical applications created in this period."
        )
    if period_kpis["active_pipeline"] and period_kpis["rejected"]:
        insights.append(
            f"Rejection rate in period: "
            f"{round((period_kpis['rejected'] / max(period_kpis['total_applications'], 1)) * 100, 1)}%."
        )
    if not pipeline_distribution and period_kpis["total_applications"] == 0:
        insights.append("No applications were created in the selected time range.")
    return insights[:5]


def _analytics_range_query(range_key: str) -> dict:
    return {"range": range_key}


def _make_csv_response(filename: str, columns: tuple[tuple[str, str], ...], rows: list[dict]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([header for header, _key in columns])
    for row in rows:
        writer.writerow([row.get(key, "") for _header, key in columns])
    payload = buffer.getvalue()
    return Response(
        payload,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _make_sectioned_csv_response(filename: str, sections: list[tuple[str, tuple[tuple[str, str], ...], list[dict]]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for index, (title, columns, rows) in enumerate(sections):
        if index:
            writer.writerow([])
        writer.writerow([f"# {title}"])
        writer.writerow([header for header, _key in columns])
        for row in rows:
            writer.writerow([row.get(key, "") for _header, key in columns])
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _distribution_export_rows(items: list[dict], label_key: str = "label") -> list[dict]:
    return [
        {
            "label": item[label_key],
            "count": item["count"],
            "share_pct": item.get("share", ""),
        }
        for item in items
    ]


def _fetch_applications_for_export(
    cursor,
    where_sql: str,
    where_params: list,
    limit: int = REPORT_EXPORT_MAX_ROWS,
) -> list[dict]:
    cursor.execute(
        f"""
        SELECT
            id,
            business_name,
            owner_name,
            email,
            revenue,
            product,
            status,
            sub_status,
            risk_level,
            flagged_fraud,
            assigned_officer,
            created_at,
            updated_at
        FROM applications
        {where_sql}
        ORDER BY id DESC
        LIMIT ?
        """,
        (*where_params, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def _fetch_audit_history_for_export(
    cursor,
    range_key: str,
    application_id: int | None = None,
    limit: int = REPORT_EXPORT_MAX_ROWS,
) -> list[dict]:
    created_clause, created_params = _analytics_datetime_clause(range_key, "wh.created_at")
    application_clause = ""
    application_params: list = []
    if application_id is not None:
        application_clause = " AND wh.application_id = ?"
        application_params.append(application_id)

    cursor.execute(
        f"""
        SELECT
            wh.id,
            wh.application_id,
            COALESCE(a.business_name, '') AS business_name,
            wh.batch_id,
            wh.action_type,
            wh.field_name,
            wh.old_value,
            wh.new_value,
            wh.actor,
            wh.context_notes,
            wh.is_critical,
            wh.transition_warning,
            wh.created_at
        FROM workflow_history wh
        LEFT JOIN applications a ON a.id = wh.application_id
        WHERE wh.created_at IS NOT NULL AND wh.created_at != ''{created_clause}{application_clause}
        ORDER BY datetime(wh.created_at) DESC, wh.id DESC
        LIMIT ?
        """,
        (*created_params, *application_params, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def _fetch_governance_audit_summary(cursor, range_key: str) -> dict:
    created_clause, created_params = _analytics_datetime_clause(range_key, "created_at")
    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_events,
            SUM(CASE WHEN is_critical = 1 THEN 1 ELSE 0 END) AS critical_events,
            COUNT(DISTINCT batch_id) AS workflow_batches,
            COUNT(DISTINCT actor) AS unique_operators,
            COUNT(DISTINCT application_id) AS applications_touched
        FROM workflow_history
        WHERE created_at IS NOT NULL AND created_at != ''{created_clause}
        """,
        created_params,
    )
    row = cursor.fetchone()
    return {
        "total_events": row["total_events"] or 0,
        "critical_events": row["critical_events"] or 0,
        "workflow_batches": row["workflow_batches"] or 0,
        "unique_operators": row["unique_operators"] or 0,
        "applications_touched": row["applications_touched"] or 0,
    }


def _fetch_fraud_review_summary(cursor) -> dict:
    cursor.execute(
        """
        SELECT
            COUNT(*) AS fraud_flagged_total,
            SUM(CASE WHEN status IN ({}) THEN 1 ELSE 0 END) AS fraud_in_pipeline
        FROM applications
        WHERE flagged_fraud = 1
        """.format(", ".join("?" * len(KPI_ACTIVE_PIPELINE_STATUSES))),
        KPI_ACTIVE_PIPELINE_STATUSES,
    )
    row = cursor.fetchone()
    return {
        "fraud_flagged_total": row["fraud_flagged_total"] or 0,
        "fraud_in_pipeline": row["fraud_in_pipeline"] or 0,
    }


def _report_executive_summary(
    portfolio_kpis: dict,
    period_kpis: dict,
    backlog: dict,
    governance: dict,
    range_label: str,
) -> list[str]:
    lines = [
        f"Reporting period: {range_label}.",
        (
            f"Portfolio: {portfolio_kpis['total_applications']} applications, "
            f"{portfolio_kpis['active_pipeline']} in active pipeline, "
            f"{portfolio_kpis['fraud_flagged']} fraud-flagged."
        ),
        (
            f"Period intake: {period_kpis['total_applications']} created; "
            f"{period_kpis['approved']} approved-stage, {period_kpis['rejected']} rejected, "
            f"{period_kpis['high_risk']} high/critical risk."
        ),
    ]
    if backlog["bottleneck_stage"]:
        lines.append(
            f"Live backlog bottleneck: {backlog['bottleneck_stage']} "
            f"({backlog['bottleneck_count']} cases)."
        )
    if governance["workflow_batches"]:
        lines.append(
            f"Governance: {governance['workflow_batches']} workflow batches, "
            f"{governance['critical_events']} critical audit events in period."
        )
    return lines[:6]


def _build_reports_page_data(cursor, range_key: str) -> dict:
    portfolio_kpis = _fetch_executive_kpis(cursor)
    period_kpis = _fetch_analytics_period_kpis(cursor, range_key)
    status_distribution = _fetch_analytics_distribution(
        cursor, range_key, group_column="status", order_values=APPLICATION_STATUSES
    )
    risk_distribution = _fetch_analytics_distribution(
        cursor, range_key, group_column="risk_level", order_values=APPLICATION_RISK_LEVELS
    )
    pipeline_distribution = _fetch_analytics_pipeline_distribution(cursor, range_key)
    officer_workload = _fetch_analytics_officer_workload(cursor, range_key)
    backlog = _fetch_analytics_backlog_snapshot(cursor)
    activity_summary = _fetch_analytics_activity_summary(cursor, range_key)
    governance = _fetch_governance_audit_summary(cursor, range_key)
    fraud_summary = _fetch_fraud_review_summary(cursor)

    portfolio_status = _fetch_status_distribution(cursor)
    portfolio_risk = _fetch_risk_distribution(cursor)
    total_portfolio = portfolio_kpis["total_applications"] or 1
    for item in portfolio_status:
        item["share"] = round((item["count"] / total_portfolio) * 100, 1)
    for item in portfolio_risk:
        item["share"] = round((item["count"] / total_portfolio) * 100, 1)

    outcome_summary = {
        "portfolio_approved": portfolio_kpis["approved"],
        "portfolio_rejected": portfolio_kpis["rejected"],
        "portfolio_pipeline": portfolio_kpis["active_pipeline"],
        "period_approved": period_kpis["approved"],
        "period_rejected": period_kpis["rejected"],
        "period_pipeline": period_kpis["active_pipeline"],
        "period_total": period_kpis["total_applications"],
    }
    if period_kpis["total_applications"]:
        outcome_summary["period_rejection_rate"] = round(
            (period_kpis["rejected"] / period_kpis["total_applications"]) * 100,
            1,
        )
    else:
        outcome_summary["period_rejection_rate"] = 0.0

    executive_lines = _report_executive_summary(
        portfolio_kpis,
        period_kpis,
        backlog,
        governance,
        ANALYTICS_TIME_RANGES[range_key],
    )

    return {
        "portfolio_kpis": portfolio_kpis,
        "period_kpis": period_kpis,
        "status_distribution": status_distribution,
        "risk_distribution": risk_distribution,
        "pipeline_distribution": pipeline_distribution,
        "portfolio_status": portfolio_status,
        "portfolio_risk": portfolio_risk,
        "officer_workload": officer_workload,
        "backlog": backlog,
        "activity_summary": activity_summary,
        "governance": governance,
        "fraud_summary": fraud_summary,
        "outcome_summary": outcome_summary,
        "executive_lines": executive_lines,
    }


def _report_export_urls(range_key: str, filter_query: dict | None = None) -> dict[str, str]:
    range_params = {"range": range_key}
    filter_params = {**(filter_query or {}), **range_params}
    return {
        "operational": url_for("admin_export_report", report_type="operational", **range_params),
        "pipeline": url_for("admin_export_report", report_type="pipeline", **range_params),
        "outcomes": url_for("admin_export_report", report_type="outcomes", **range_params),
        "risk": url_for("admin_export_report", report_type="risk", **range_params),
        "fraud": url_for("admin_export_report", report_type="fraud", **range_params),
        "officers": url_for("admin_export_report", report_type="officers", **range_params),
        "backlog": url_for("admin_export_report", report_type="backlog", **range_params),
        "audit": url_for("admin_export_audit", **range_params),
        "applications_filtered": url_for("admin_export_applications", **filter_params),
        "applications_all": url_for("admin_export_applications", **range_params),
    }


@app.template_global()
def dashboard_risk_badge_class(risk_level: str) -> str:
    mapping = {
        "Low": "dashboard-badge-risk-low",
        "Medium": "dashboard-badge-risk-medium",
        "High": "dashboard-badge-risk-high",
        "Critical": "dashboard-badge-risk-critical",
    }
    return mapping.get(risk_level, "dashboard-badge-risk-neutral")


@app.template_global()
def dashboard_status_badge_class(status: str) -> str:
    if status == KPI_REJECTED_STATUS:
        return "dashboard-badge-status-rejected"
    if status in KPI_APPROVED_STATUSES:
        return "dashboard-badge-status-approved"
    if status in KPI_PENDING_STATUSES:
        return "dashboard-badge-status-pending"
    return "dashboard-badge-status-neutral"


@app.template_global()
def dashboard_table_row_class(application) -> str:
    classes = []
    if application["flagged_fraud"]:
        classes.append("dashboard-table-row-fraud")
    elif application["risk_level"] in KPI_HIGH_RISK_LEVELS:
        classes.append("dashboard-table-row-high-risk")
    elif _application_needs_attention(application):
        classes.append("dashboard-table-row-attention")
    return " ".join(classes)


@app.template_global()
def dashboard_workflow_status_groups():
    return WORKFLOW_STATUS_GROUPS


@app.template_global()
def dashboard_workflow_sub_status_groups():
    return WORKFLOW_SUB_STATUS_GROUPS


@app.template_global()
def dashboard_history_batch_class(batch: dict) -> str:
    classes: list[str] = []
    if batch.get("is_critical"):
        classes.append("dashboard-history-batch-critical")
    if batch.get("transition_warning"):
        classes.append("dashboard-history-batch-warning")
    return " ".join(classes)


@app.template_global()
def dashboard_history_action_label(action_type: str) -> str:
    labels = {
        "application_created": "Application created",
        "workflow_update": "Workflow update",
        "quick_action_advance": "Quick action: advance status",
        "quick_action_margin_to_act": "Quick action: Margin to act",
        "quick_action_clear_sub_status": "Quick action: clear sub-status",
        "quick_action_high_risk": "Quick action: set high risk",
        "quick_action_clear_fraud": "Quick action: clear fraud flag",
        "status_change": "Status change",
        "sub_status_change": "Sub-status change",
        "risk_level_change": "Risk level change",
        "fraud_flag_change": "Fraud flag change",
        "officer_assignment": "Officer assignment",
        "notes_update": "Notes update",
    }
    return labels.get(action_type, action_type.replace("_", " ").title())


def _fetch_application(application_id: int) -> sqlite3.Row | None:
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM applications WHERE id = ?", (application_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def _normalize_sub_status(raw_value: str) -> str | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    return value if value in APPLICATION_SUB_STATUSES else None


def _normalize_officer_name(raw_value: str) -> str:
    collapsed = " ".join((raw_value or "").split())
    if not collapsed:
        return ""
    if not OFFICER_NAME_PATTERN.match(collapsed):
        return ""
    return collapsed[:MAX_ASSIGNED_OFFICER_LENGTH]


def _parse_flagged_fraud(raw_value: str) -> int:
    return 1 if (raw_value or "").strip() in {"1", "true", "on", "yes"} else 0


def _is_allowed_status_transition(current_status: str, next_status: str) -> bool:
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


def _next_pipeline_status(current_status: str) -> str | None:
    if current_status not in KPI_ACTIVE_PIPELINE_STATUSES:
        return None
    index = APPLICATION_STATUSES.index(current_status)
    if index + 1 < len(APPLICATION_STATUSES):
        candidate = APPLICATION_STATUSES[index + 1]
        if candidate in KPI_ACTIVE_PIPELINE_STATUSES:
            return candidate
    return None


def _workflow_row_signature(row: sqlite3.Row) -> tuple:
    return (
        row["status"],
        row["sub_status"],
        row["risk_level"],
        row["assigned_officer"] or "",
        row["approval_notes"] or "",
        int(row["flagged_fraud"] or 0),
    )


def _validate_workflow_form(data, current: sqlite3.Row | None = None) -> tuple[dict | None, str | None]:
    status = (data.get("status") or "").strip()
    if status not in APPLICATION_STATUSES:
        return None, "Select a valid workflow status."

    sub_status = _normalize_sub_status(data.get("sub_status", ""))
    if (data.get("sub_status") or "").strip() and sub_status is None:
        return None, "Select a valid sub-status or leave it blank."

    risk_level = (data.get("risk_level") or "").strip()
    if risk_level not in APPLICATION_RISK_LEVELS:
        return None, "Select a valid risk level."

    assigned_officer = _normalize_officer_name(data.get("assigned_officer", ""))
    if (data.get("assigned_officer") or "").strip() and not assigned_officer:
        return None, "Officer name can only include letters, numbers, spaces, and . ' -"

    approval_notes = (data.get("approval_notes") or "").strip()
    if len(approval_notes) > MAX_APPROVAL_NOTES_LENGTH:
        return None, f"Notes must be {MAX_APPROVAL_NOTES_LENGTH} characters or fewer."

    if current is not None and not _is_allowed_status_transition(current["status"], status):
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
        "flagged_fraud": _parse_flagged_fraud(data.get("flagged_fraud", "")),
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
        if proposed == _workflow_row_signature(current):
            return None, "No workflow changes were detected."

    return workflow, None


def _apply_workflow_quick_action(form_data, current: sqlite3.Row) -> tuple[dict | None, str | None]:
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
        next_status = _next_pipeline_status(current["status"])
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

    return _validate_workflow_form(payload, current)


def _filters_have_constraints(filters: dict) -> bool:
    return any(filters.get(key) for key in ADMIN_LIST_FILTER_KEYS)


def _active_filter_chips(filters: dict) -> list[dict]:
    chips: list[dict] = []
    preset = filters.get("preset") or ""
    if preset in ADMIN_FILTER_PRESETS:
        chips.append(
            {
                "label": ADMIN_FILTER_PRESETS[preset],
                "clear_url": url_for("admin", **{k: v for k, v in _filters_to_query_params(filters).items() if k != "preset"}),
            }
        )
    if filters.get("status"):
        chips.append(
            {
                "label": f"Status: {filters['status']}",
                "clear_url": url_for("admin", **{k: v for k, v in _filters_to_query_params(filters).items() if k != "status"}),
            }
        )
    if filters.get("sub_status"):
        chips.append(
            {
                "label": f"Sub-status: {filters['sub_status']}",
                "clear_url": url_for("admin", **{k: v for k, v in _filters_to_query_params(filters).items() if k != "sub_status"}),
            }
        )
    if filters.get("risk_level"):
        chips.append(
            {
                "label": f"Risk: {filters['risk_level']}",
                "clear_url": url_for("admin", **{k: v for k, v in _filters_to_query_params(filters).items() if k != "risk_level"}),
            }
        )
    if filters.get("flagged_fraud") == "1":
        chips.append(
            {
                "label": "Fraud flagged",
                "clear_url": url_for("admin", **{k: v for k, v in _filters_to_query_params(filters).items() if k != "flagged_fraud"}),
            }
        )
    elif filters.get("flagged_fraud") == "0":
        chips.append(
            {
                "label": "Not fraud flagged",
                "clear_url": url_for("admin", **{k: v for k, v in _filters_to_query_params(filters).items() if k != "flagged_fraud"}),
            }
        )
    if filters.get("assigned_officer"):
        chips.append(
            {
                "label": f"Officer: {filters['assigned_officer']}",
                "clear_url": url_for(
                    "admin",
                    **{k: v for k, v in _filters_to_query_params(filters).items() if k != "assigned_officer"},
                ),
            }
        )
    if filters.get("q"):
        chips.append(
            {
                "label": f"Search: “{filters['q']}”",
                "clear_url": url_for("admin", **{k: v for k, v in _filters_to_query_params(filters).items() if k != "q"}),
            }
        )
    return chips


def _safe_return_url(candidate: str | None) -> str:
    value = (candidate or "").strip()
    if value.startswith("/admin"):
        return value
    return url_for("admin")


def _application_needs_attention(row) -> bool:
    if row["flagged_fraud"]:
        return True
    if row["risk_level"] in KPI_HIGH_RISK_LEVELS:
        return True
    if row["sub_status"] == KPI_OPS_REVIEW_SUB_STATUS:
        return True
    if row["status"] in KPI_ACTIVE_PIPELINE_STATUSES and not (row["assigned_officer"] or "").strip():
        return True
    return False


@app.route('/')
def home():
    csrf_token = _ensure_session_csrf_token()
    return render_template('index.html', csrf_token=csrf_token)

@app.route('/apply', methods=['POST'])
def apply():
    data = request.form
    if not _validate_csrf(data.get("csrf_token", "")):
        return redirect('/')

    if not _is_valid_application_form(data):
        return redirect('/')

    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO applications (
            business_name,
            owner_name,
            email,
            revenue,
            product,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (
            data["business_name"].strip(),
            data["owner_name"].strip(),
            data["email"].strip(),
            data["revenue"],
            data["product"].strip(),
            DEFAULT_APPLICATION_STATUS,
        ),
    )
    application_id = cursor.lastrowid
    _log_application_created(cursor, application_id)

    conn.commit()
    conn.close()

    return redirect('/')

@app.route("/admin/overview")
@require_admin_auth
def admin_overview():
    conn = _get_db_connection()
    cursor = conn.cursor()

    kpis = _fetch_executive_kpis(cursor)
    status_distribution = _fetch_status_distribution(cursor)
    risk_distribution = _fetch_risk_distribution(cursor)
    pipeline_backlog = _fetch_pipeline_backlog(cursor)
    officer_workload = _fetch_officer_workload(cursor)
    recent_applications = _fetch_recent_applications(cursor)
    attention_applications = _fetch_attention_applications(cursor)

    conn.close()

    total_for_bars = kpis["total_applications"] or 1
    for item in status_distribution:
        item["share"] = round((item["count"] / total_for_bars) * 100, 1)
    for item in risk_distribution:
        item["share"] = round((item["count"] / total_for_bars) * 100, 1)

    pipeline_total = sum(item["count"] for item in pipeline_backlog)
    pipeline_denominator = pipeline_total or 1
    for item in pipeline_backlog:
        item["share"] = round((item["count"] / pipeline_denominator) * 100, 1)

    return render_template(
        "overview.html",
        kpis=kpis,
        kpi_links=_overview_drilldown_links(),
        status_distribution=status_distribution,
        risk_distribution=risk_distribution,
        pipeline_backlog=pipeline_backlog,
        pipeline_total=pipeline_total,
        officer_workload=officer_workload,
        recent_applications=recent_applications,
        attention_applications=attention_applications,
        active_nav="overview",
        page_title="Operations Overview",
        portfolio_empty=kpis["total_applications"] == 0,
    )


@app.route("/admin/analytics")
@require_admin_auth
def admin_analytics():
    range_key = _parse_analytics_range(request.args)

    conn = _get_db_connection()
    cursor = conn.cursor()

    period_kpis = _fetch_analytics_period_kpis(cursor, range_key)
    intake_trend = _fetch_analytics_intake_trend(cursor, range_key)
    fraud_trend = _fetch_analytics_fraud_trend(cursor, range_key)
    outcome_trend = _fetch_analytics_outcome_trend(cursor, range_key)
    status_distribution = _fetch_analytics_distribution(
        cursor, range_key, group_column="status", order_values=APPLICATION_STATUSES
    )
    risk_distribution = _fetch_analytics_distribution(
        cursor, range_key, group_column="risk_level", order_values=APPLICATION_RISK_LEVELS
    )
    pipeline_distribution = _fetch_analytics_pipeline_distribution(cursor, range_key)
    officer_workload = _fetch_analytics_officer_workload(cursor, range_key)
    backlog = _fetch_analytics_backlog_snapshot(cursor)
    activity_summary = _fetch_analytics_activity_summary(cursor, range_key)

    conn.close()

    insights = _analytics_insights(period_kpis, backlog, officer_workload, pipeline_distribution)

    return render_template(
        "analytics.html",
        range_key=range_key,
        range_label=ANALYTICS_TIME_RANGES[range_key],
        time_ranges=ANALYTICS_TIME_RANGES,
        export_urls=_report_export_urls(range_key),
        period_kpis=period_kpis,
        intake_trend=intake_trend,
        fraud_trend=fraud_trend,
        outcome_trend=outcome_trend,
        status_distribution=status_distribution,
        risk_distribution=risk_distribution,
        pipeline_distribution=pipeline_distribution,
        officer_workload=officer_workload,
        backlog=backlog,
        activity_summary=activity_summary,
        insights=insights,
        active_nav="analytics",
        page_title="Operational Analytics",
        portfolio_empty=period_kpis["total_applications"] == 0,
    )


@app.route("/admin/reports")
@require_admin_auth
def admin_reports():
    range_key = _parse_analytics_range(request.args)

    conn = _get_db_connection()
    cursor = conn.cursor()
    report_data = _build_reports_page_data(cursor, range_key)
    conn.close()

    return render_template(
        "reports.html",
        active_nav="reports",
        page_title="Operational Reports",
        range_key=range_key,
        range_label=ANALYTICS_TIME_RANGES[range_key],
        time_ranges=ANALYTICS_TIME_RANGES,
        export_urls=_report_export_urls(range_key),
        portfolio_empty=report_data["portfolio_kpis"]["total_applications"] == 0,
        **report_data,
    )


@app.route("/admin/export/applications")
@require_admin_auth
def admin_export_applications():
    filters = _parse_admin_list_filters(request.args)
    where_sql, where_params = _build_applications_where(filters)

    conn = _get_db_connection()
    cursor = conn.cursor()
    rows = _fetch_applications_for_export(cursor, where_sql, where_params)
    conn.close()

    suffix = "filtered" if _filters_have_constraints(filters) else "all"
    return _make_csv_response(f"applications_{suffix}.csv", APPLICATION_EXPORT_COLUMNS, rows)


@app.route("/admin/export/audit")
@require_admin_auth
def admin_export_audit():
    range_key = _parse_analytics_range(request.args)
    application_id = None
    raw_id = (request.args.get("application_id") or "").strip()
    if raw_id.isdigit():
        application_id = int(raw_id)

    conn = _get_db_connection()
    cursor = conn.cursor()
    rows = _fetch_audit_history_for_export(cursor, range_key, application_id)
    conn.close()

    filename = f"audit_history_{range_key}"
    if application_id is not None:
        filename += f"_app_{application_id}"
    return _make_csv_response(f"{filename}.csv", AUDIT_EXPORT_COLUMNS, rows)


@app.route("/admin/export/report/<report_type>")
@require_admin_auth
def admin_export_report(report_type: str):
    if report_type not in REPORT_EXPORT_TYPES:
        return Response("Unknown report type.", status=404)

    range_key = _parse_analytics_range(request.args)
    conn = _get_db_connection()
    cursor = conn.cursor()
    data = _build_reports_page_data(cursor, range_key)
    conn.close()

    dist_columns = (("label", "label"), ("count", "count"), ("share_pct", "share_pct"))
    metric_columns = (("metric", "metric"), ("value", "value"))

    if report_type == "pipeline":
        rows = _distribution_export_rows(data["pipeline_distribution"])
        return _make_csv_response(f"pipeline_summary_{range_key}.csv", dist_columns, rows)

    if report_type == "risk":
        sections = [
            ("Period risk (created in range)", dist_columns, _distribution_export_rows(data["risk_distribution"])),
            ("Portfolio risk (live)", dist_columns, _distribution_export_rows(data["portfolio_risk"])),
        ]
        return _make_sectioned_csv_response(f"risk_exposure_{range_key}.csv", sections)

    if report_type == "outcomes":
        outcome = data["outcome_summary"]
        rows = [
            {"metric": "Portfolio — active pipeline", "value": outcome["portfolio_pipeline"]},
            {"metric": "Portfolio — approved", "value": outcome["portfolio_approved"]},
            {"metric": "Portfolio — rejected", "value": outcome["portfolio_rejected"]},
            {"metric": f"Period ({range_key}) — applications created", "value": outcome["period_total"]},
            {"metric": f"Period ({range_key}) — approved-stage created", "value": outcome["period_approved"]},
            {"metric": f"Period ({range_key}) — rejected created", "value": outcome["period_rejected"]},
            {"metric": f"Period ({range_key}) — rejection rate %", "value": outcome["period_rejection_rate"]},
        ]
        status_rows = _distribution_export_rows(data["status_distribution"])
        sections = [
            ("Approval and rejection summary", metric_columns, rows),
            ("Period status distribution", dist_columns, status_rows),
        ]
        return _make_sectioned_csv_response(f"approval_outcomes_{range_key}.csv", sections)

    if report_type == "fraud":
        fraud = data["fraud_summary"]
        summary_rows = [
            {"metric": "Fraud-flagged (portfolio)", "value": fraud["fraud_flagged_total"]},
            {"metric": "Fraud-flagged in active pipeline", "value": fraud["fraud_in_pipeline"]},
            {"metric": f"Fraud-flagged created in period ({range_key})", "value": data["period_kpis"]["fraud_flagged"]},
        ]
        conn = _get_db_connection()
        cursor = conn.cursor()
        fraud_apps = _fetch_applications_for_export(
            cursor,
            " WHERE flagged_fraud = 1",
            [],
        )
        conn.close()
        sections = [
            ("Fraud review summary", metric_columns, summary_rows),
            ("Fraud-flagged applications", APPLICATION_EXPORT_COLUMNS, fraud_apps),
        ]
        return _make_sectioned_csv_response(f"fraud_review_{range_key}.csv", sections)

    if report_type == "officers":
        rows = [
            {
                "officer": item["officer"],
                "total_count": item["total_count"],
                "pipeline_count": item["pipeline_count"],
                "fraud_count": item["fraud_count"],
                "load_share_pct": item.get("load_share", ""),
            }
            for item in data["officer_workload"]
        ]
        officer_columns = (
            ("officer", "officer"),
            ("total_count", "total_count"),
            ("pipeline_count", "pipeline_count"),
            ("fraud_count", "fraud_count"),
            ("load_share_pct", "load_share_pct"),
        )
        return _make_csv_response(f"officer_workload_{range_key}.csv", officer_columns, rows)

    if report_type == "backlog":
        rows = _distribution_export_rows(data["backlog"]["pipeline_backlog"])
        summary_rows = [
            {"metric": "Live pipeline backlog total", "value": data["backlog"]["pipeline_total"]},
            {"metric": "Bottleneck stage", "value": data["backlog"]["bottleneck_stage"] or "—"},
            {"metric": "Bottleneck count", "value": data["backlog"]["bottleneck_count"]},
        ]
        sections = [
            ("Backlog summary", metric_columns, summary_rows),
            ("Pipeline stage backlog", dist_columns, rows),
        ]
        return _make_sectioned_csv_response(f"operational_backlog_{range_key}.csv", sections)

    # operational — bundled executive export
    gov = data["governance"]
    executive_rows = [{"summary": line} for line in data["executive_lines"]]
    governance_rows = [
        {"metric": "Workflow batches in period", "value": gov["workflow_batches"]},
        {"metric": "Audit events in period", "value": gov["total_events"]},
        {"metric": "Critical audit events", "value": gov["critical_events"]},
        {"metric": "Unique operators", "value": gov["unique_operators"]},
        {"metric": "Applications with audit activity", "value": gov["applications_touched"]},
        {"metric": "Workflow updates (distinct batches)", "value": data["activity_summary"]["updates_in_period"]},
    ]
    sections = [
        ("Executive summary", (("summary", "summary"),), executive_rows),
        ("Governance and audit", metric_columns, governance_rows),
        ("Pipeline distribution (period)", dist_columns, _distribution_export_rows(data["pipeline_distribution"])),
        (
            "Officer workload (period)",
            (
                ("officer", "officer"),
                ("pipeline_count", "pipeline_count"),
                ("total_count", "total_count"),
            ),
            [
                {
                    "officer": item["officer"],
                    "pipeline_count": item["pipeline_count"],
                    "total_count": item["total_count"],
                }
                for item in data["officer_workload"]
            ],
        ),
    ]
    return _make_sectioned_csv_response(f"operational_report_{range_key}.csv", sections)


@app.route('/admin')
@require_admin_auth
def admin():
    filters = _parse_admin_list_filters(request.args)
    where_sql, where_params = _build_applications_where(filters)

    conn = _get_db_connection()
    cursor = conn.cursor()

    kpis = _fetch_application_kpis(cursor)
    officers = _fetch_distinct_officers(cursor)

    cursor.execute(f"SELECT COUNT(*) AS total FROM applications{where_sql}", where_params)
    total_matching = cursor.fetchone()["total"] or 0

    total_pages = max(1, (total_matching + ADMIN_PAGE_SIZE - 1) // ADMIN_PAGE_SIZE)
    page = min(filters["page"], total_pages)
    offset = (page - 1) * ADMIN_PAGE_SIZE

    cursor.execute(
        f"""
        SELECT
            id,
            business_name,
            owner_name,
            email,
            revenue,
            product,
            status,
            sub_status,
            risk_level,
            flagged_fraud,
            assigned_officer
        FROM applications
        {where_sql}
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (*where_params, ADMIN_PAGE_SIZE, offset),
    )
    applications = cursor.fetchall()
    conn.close()

    pagination = {
        "page": page,
        "total_pages": total_pages,
        "total_matching": total_matching,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "page_size": ADMIN_PAGE_SIZE,
    }

    preset = filters.get("preset") or ""
    filter_preset_label = ADMIN_FILTER_PRESETS.get(preset, "")
    if not filter_preset_label and filters.get("flagged_fraud") == "1":
        filter_preset_label = "Fraud-flagged applications"

    portfolio_empty = kpis["total_applications"] == 0
    filters_active = _filters_have_constraints(filters)

    filter_query = _filters_to_query_params(filters)

    return render_template(
        "dashboard.html",
        applications=applications,
        filters=filters,
        kpis=kpis,
        kpi_links=_overview_drilldown_links(),
        pagination=pagination,
        filter_query=filter_query,
        export_applications_url=url_for("admin_export_applications", **filter_query),
        filter_preset_label=filter_preset_label,
        active_filter_chips=_active_filter_chips(filters),
        filters_active=filters_active,
        portfolio_empty=portfolio_empty,
        statuses=APPLICATION_STATUSES,
        sub_statuses=APPLICATION_SUB_STATUSES,
        risk_levels=APPLICATION_RISK_LEVELS,
        officers=officers,
        active_nav="applications",
        page_title="Applications",
    )


@app.route("/admin/applications/<int:application_id>")
@require_admin_auth
def admin_application_detail(application_id: int):
    application = _fetch_application(application_id)
    if application is None:
        return Response("Application not found.", status=404)

    conn = _get_db_connection()
    cursor = conn.cursor()
    history_rows = _fetch_workflow_history_rows(cursor, application_id)
    officers = _fetch_registered_officers(cursor)
    conn.close()

    csrf_token = _ensure_session_csrf_token()
    next_status = _next_pipeline_status(application["status"])
    status_transition_hint = _is_risky_status_transition_warning(
        application["status"],
        next_status or application["status"],
    )
    return render_template(
        "application_detail.html",
        application=application,
        csrf_token=csrf_token,
        statuses=APPLICATION_STATUSES,
        sub_statuses=APPLICATION_SUB_STATUSES,
        risk_levels=APPLICATION_RISK_LEVELS,
        officers=officers,
        next_pipeline_status=next_status,
        needs_attention=_application_needs_attention(application),
        timeline_batches=_group_workflow_history_batches(history_rows),
        admin_actor=getattr(g, "admin_actor", _get_request_actor()),
        status_transition_hint=status_transition_hint,
        export_audit_url=url_for(
            "admin_export_audit",
            application_id=application_id,
            range="all",
        ),
        active_nav="applications",
        page_title=f"Application #{application_id}",
        list_return_url=_safe_return_url(request.args.get("return")),
    )


@app.route("/admin/applications/<int:application_id>/workflow", methods=["POST"])
@require_admin_auth
def admin_application_workflow(application_id: int):
    if not _validate_csrf(request.form.get("csrf_token", "")):
        flash("Security check failed. Please try again.", "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    application = _fetch_application(application_id)
    if application is None:
        return Response("Application not found.", status=404)

    actor = getattr(g, "admin_actor", _get_request_actor())
    action = (request.form.get("workflow_action") or "").strip()

    conn = _get_db_connection()
    cursor = conn.cursor()
    officers = _fetch_registered_officers(cursor)
    conn.close()

    if action:
        workflow, validation_error = _apply_workflow_quick_action(request.form, application)
    else:
        workflow, validation_error = _validate_workflow_form(request.form, application)

    if validation_error:
        category = "info" if validation_error.startswith("No workflow changes") else "error"
        flash(validation_error, category)
        return redirect(url_for("admin_application_detail", application_id=application_id))

    if workflow is None:
        flash("Could not save workflow changes. Check the form and try again.", "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    workflow["assigned_officer"] = _resolve_officer_name(workflow["assigned_officer"], officers)

    before_snapshot = _workflow_snapshot_from_row(application)
    after_snapshot = _workflow_snapshot_from_workflow(workflow)
    audit_required = _requires_audit_context(before_snapshot, after_snapshot, action or None)
    context_notes, audit_error = _validate_audit_context(
        request.form.get("audit_context", ""),
        audit_required,
    )
    if audit_error:
        flash(audit_error, "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    transition_warning = None
    if before_snapshot["status"] != after_snapshot["status"]:
        transition_warning = _is_risky_status_transition_warning(
            before_snapshot["status"],
            after_snapshot["status"],
        )

    _persist_workflow_update(
        application_id,
        application,
        workflow,
        actor,
        quick_action=action or None,
        context_notes=context_notes,
        transition_warning=transition_warning,
    )

    flash_message = (
        f"Workflow saved for application #{application_id} — status is now “{workflow['status']}”. "
        f"Recorded under operator “{actor}”."
    )
    if transition_warning:
        flash_message += f" Note: {transition_warning}"
    flash(flash_message, "success")
    if not workflow["assigned_officer"] and workflow["status"] in KPI_ACTIVE_PIPELINE_STATUSES:
        flash(
            "This pipeline case has no assigned officer. Assign one for operational accountability.",
            "info",
        )
    return redirect(url_for("admin_application_detail", application_id=application_id))


if __name__ == '__main__':
    if not _is_development() and app.config["SECRET_KEY"] == "dev-only-secret-key-change-me":
        raise RuntimeError("Set a strong SECRET_KEY environment variable for non-development environments.")

    init_db()
    debug_mode = _is_development() and _get_bool_env("FLASK_DEBUG", default=True)
    app.run(debug=debug_mode)