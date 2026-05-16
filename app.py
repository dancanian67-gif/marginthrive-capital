import base64
import hmac
import os
from datetime import date, timedelta

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
    cursor.execute(
        """
        SELECT DISTINCT assigned_officer
        FROM applications
        WHERE assigned_officer IS NOT NULL AND TRIM(assigned_officer) != ''
        ORDER BY assigned_officer COLLATE NOCASE ASC
        """
    )
    return [row["assigned_officer"] for row in cursor.fetchall()]


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
    updated_clause, updated_params = _analytics_datetime_clause(range_key, "updated_at")
    cursor.execute(
        f"""
        SELECT COUNT(*) AS updates_in_period
        FROM applications
        WHERE updated_at IS NOT NULL AND updated_at != ''{updated_clause}
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
    return render_template(
        "reports.html",
        active_nav="reports",
        page_title="Reports",
    )


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

    return render_template(
        "dashboard.html",
        applications=applications,
        filters=filters,
        kpis=kpis,
        kpi_links=_overview_drilldown_links(),
        pagination=pagination,
        filter_query=_filters_to_query_params(filters),
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

    csrf_token = _ensure_session_csrf_token()
    next_status = _next_pipeline_status(application["status"])
    return render_template(
        "application_detail.html",
        application=application,
        csrf_token=csrf_token,
        statuses=APPLICATION_STATUSES,
        sub_statuses=APPLICATION_SUB_STATUSES,
        risk_levels=APPLICATION_RISK_LEVELS,
        next_pipeline_status=next_status,
        needs_attention=_application_needs_attention(application),
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

    action = (request.form.get("workflow_action") or "").strip()
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

    flash(
        f"Workflow saved for application #{application_id} — status is now “{workflow['status']}”.",
        "success",
    )
    return redirect(url_for("admin_application_detail", application_id=application_id))


if __name__ == '__main__':
    if not _is_development() and app.config["SECRET_KEY"] == "dev-only-secret-key-change-me":
        raise RuntimeError("Set a strong SECRET_KEY environment variable for non-development environments.")

    init_db()
    debug_mode = _is_development() and _get_bool_env("FLASK_DEBUG", default=True)
    app.run(debug=debug_mode)