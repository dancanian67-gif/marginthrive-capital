import base64
import hmac
import os

from dotenv import load_dotenv

load_dotenv()
import re
import secrets
import sqlite3
from functools import wraps

from flask import Flask, Response, flash, redirect, render_template, request, session, url_for

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

ADMIN_PAGE_SIZE = 15
ADMIN_SEARCH_MAX_LENGTH = 100

ADMIN_LIST_FILTER_KEYS = (
    "status",
    "sub_status",
    "risk_level",
    "flagged_fraud",
    "assigned_officer",
    "q",
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


def _check_admin_auth(auth_header: str | None) -> bool:
    if not auth_header or not auth_header.startswith("Basic "):
        return False

    expected_username = os.getenv("ADMIN_USERNAME")
    expected_password = os.getenv("ADMIN_PASSWORD")
    if not expected_username or not expected_password:
        return False

    try:
        encoded_credentials = auth_header.split(" ", 1)[1]
        decoded = base64.b64decode(encoded_credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return False

    return hmac.compare_digest(username, expected_username) and hmac.compare_digest(password, expected_password)


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

    conn.commit()
    conn.close()


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
        "page": page,
    }


def _build_applications_where(filters: dict) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []

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


def _fetch_application_kpis(cursor) -> dict:
    pending_placeholders = ", ".join("?" * len(KPI_PENDING_STATUSES))
    approved_placeholders = ", ".join("?" * len(KPI_APPROVED_STATUSES))
    high_risk_placeholders = ", ".join("?" * len(KPI_HIGH_RISK_LEVELS))

    cursor.execute(
        f"""
        SELECT
            COUNT(*) AS total_applications,
            SUM(CASE WHEN status IN ({pending_placeholders}) THEN 1 ELSE 0 END) AS pending_review,
            SUM(CASE WHEN status IN ({approved_placeholders}) THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS rejected,
            SUM(CASE WHEN risk_level IN ({high_risk_placeholders}) THEN 1 ELSE 0 END) AS high_risk,
            SUM(CASE WHEN flagged_fraud = 1 THEN 1 ELSE 0 END) AS fraud_flagged
        FROM applications
        """,
        (
            *KPI_PENDING_STATUSES,
            *KPI_APPROVED_STATUSES,
            KPI_REJECTED_STATUS,
            *KPI_HIGH_RISK_LEVELS,
        ),
    )
    row = cursor.fetchone()
    return {
        "total_applications": row["total_applications"] or 0,
        "pending_review": row["pending_review"] or 0,
        "approved": row["approved"] or 0,
        "rejected": row["rejected"] or 0,
        "high_risk": row["high_risk"] or 0,
        "fraud_flagged": row["fraud_flagged"] or 0,
    }


def _fetch_distinct_officers(cursor) -> list[str]:
    cursor.execute(
        """
        SELECT DISTINCT assigned_officer
        FROM applications
        WHERE assigned_officer IS NOT NULL AND TRIM(assigned_officer) != ''
        ORDER BY assigned_officer COLLATE NOCASE ASC
        """
    )
    return [row["assigned_officer"] for row in cursor.fetchall()]


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


def _parse_flagged_fraud(raw_value: str) -> int:
    return 1 if (raw_value or "").strip() in {"1", "true", "on", "yes"} else 0


def _validate_workflow_form(data) -> dict | None:
    status = (data.get("status") or "").strip()
    if status not in APPLICATION_STATUSES:
        return None

    sub_status = _normalize_sub_status(data.get("sub_status", ""))
    if (data.get("sub_status") or "").strip() and sub_status is None:
        return None

    risk_level = (data.get("risk_level") or "").strip()
    if risk_level not in APPLICATION_RISK_LEVELS:
        return None

    assigned_officer = (data.get("assigned_officer") or "").strip()
    if len(assigned_officer) > MAX_ASSIGNED_OFFICER_LENGTH:
        return None

    approval_notes = (data.get("approval_notes") or "").strip()
    if len(approval_notes) > MAX_APPROVAL_NOTES_LENGTH:
        return None

    return {
        "status": status,
        "sub_status": sub_status,
        "risk_level": risk_level,
        "assigned_officer": assigned_officer,
        "approval_notes": approval_notes,
        "flagged_fraud": _parse_flagged_fraud(data.get("flagged_fraud", "")),
    }


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

    conn.commit()
    conn.close()

    return redirect('/')

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

    return render_template(
        "dashboard.html",
        applications=applications,
        filters=filters,
        kpis=kpis,
        pagination=pagination,
        filter_query=_filters_to_query_params(filters),
        statuses=APPLICATION_STATUSES,
        sub_statuses=APPLICATION_SUB_STATUSES,
        risk_levels=APPLICATION_RISK_LEVELS,
        officers=officers,
        active_nav="applications",
    )


@app.route("/admin/applications/<int:application_id>")
@require_admin_auth
def admin_application_detail(application_id: int):
    application = _fetch_application(application_id)
    if application is None:
        return Response("Application not found.", status=404)

    csrf_token = _ensure_session_csrf_token()
    return render_template(
        "application_detail.html",
        application=application,
        csrf_token=csrf_token,
        statuses=APPLICATION_STATUSES,
        sub_statuses=APPLICATION_SUB_STATUSES,
        risk_levels=APPLICATION_RISK_LEVELS,
        active_nav="applications",
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

    workflow = _validate_workflow_form(request.form)
    if workflow is None:
        flash("Invalid workflow data. No changes were saved.", "error")
        return redirect(url_for("admin_application_detail", application_id=application_id))

    conn = _get_db_connection()
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()

    flash("Workflow updated successfully.", "success")
    return redirect(url_for("admin_application_detail", application_id=application_id))


if __name__ == '__main__':
    if not _is_development() and app.config["SECRET_KEY"] == "dev-only-secret-key-change-me":
        raise RuntimeError("Set a strong SECRET_KEY environment variable for non-development environments.")

    init_db()
    debug_mode = _is_development() and _get_bool_env("FLASK_DEBUG", default=True)
    app.run(debug=debug_mode)