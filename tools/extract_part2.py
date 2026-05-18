from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L = (ROOT / "app.py").read_text(encoding="utf-8").splitlines()


def g(a, b):
    return "\n".join(L[a - 1 : b]) + "\n"


def subs(body, mapping):
    for o, n in mapping.items():
        body = body.replace(o, n)
    return body


# services/filters.py
body = g(930, 1042) + g(2112, 2185)
body = subs(body, {
    "def _parse_admin_list_filters": "def parse_admin_list_filters",
    "def _build_applications_where": "def build_applications_where",
    "def _filters_to_query_params": "def filters_to_query_params",
    "def _filters_have_constraints": "def filters_have_constraints",
    "def _active_filter_chips": "def active_filter_chips",
    "def _safe_return_url": "def safe_return_url",
})
header = """from flask import url_for

from constants.workflow import (
    ADMIN_FILTER_PRESETS,
    ADMIN_LIST_FILTER_KEYS,
    ADMIN_SEARCH_MAX_LENGTH,
    APPLICATION_RISK_LEVELS,
    APPLICATION_STATUSES,
    APPLICATION_SUB_STATUSES,
    KPI_ACTIVE_PIPELINE_STATUSES,
    KPI_APPROVED_STATUSES,
    KPI_CLIENT_ACTION_SUB_STATUSES,
    KPI_HIGH_RISK_LEVELS,
    KPI_OPS_REVIEW_SUB_STATUS,
    KPI_REJECTED_STATUS,
    MAX_ASSIGNED_OFFICER_LENGTH,
)"""
(ROOT / "services/filters.py").write_text(header + "\n\n" + body, encoding="utf-8")
print("services/filters.py")

# repositories/applications.py
body = g(1045, 1244) + g(1642, 1671) + g(1739, 1754) + g(1948, 1954)
body = subs(body, {
    "def _fetch_executive_kpis": "def fetch_executive_kpis",
    "def _fetch_application_kpis": "def fetch_application_kpis",
    "def _fetch_status_distribution": "def fetch_status_distribution",
    "def _fetch_risk_distribution": "def fetch_risk_distribution",
    "def _fetch_pipeline_backlog": "def fetch_pipeline_backlog",
    "def _fetch_officer_workload": "def fetch_officer_workload",
    "def _fetch_recent_applications": "def fetch_recent_applications",
    "def _fetch_attention_applications": "def fetch_attention_applications",
    "def _fetch_application": "def fetch_application",
    "def _fetch_applications_for_export": "def fetch_applications_for_export",
    "def _fetch_fraud_review_summary": "def fetch_fraud_review_summary",
    "_get_db_connection()": "get_db_connection()",
    "def _get_db_connection": "def get_db_connection",
})
header = """from constants.reporting import REPORT_EXPORT_MAX_ROWS
from constants.workflow import (
    KPI_ACTIVE_PIPELINE_STATUSES,
    KPI_APPROVED_STATUSES,
    KPI_CLIENT_ACTION_SUB_STATUSES,
    KPI_HIGH_RISK_LEVELS,
    KPI_OPS_REVIEW_SUB_STATUS,
    KPI_REJECTED_STATUS,
    OVERVIEW_LIST_LIMIT,
    OVERVIEW_OFFICER_LIMIT,
)
from repositories.database import get_db_connection"""
(ROOT / "repositories/applications.py").write_text(header + "\n\n" + body, encoding="utf-8")
print("repositories/applications.py")

# services/analytics.py
body = g(1281, 1597)
body = subs(body, {
    "def _analytics_range_span_days": "def analytics_range_span_days",
    "def _add_distribution_shares": "def add_distribution_shares",
    "def _fill_daily_trend": "def fill_daily_trend",
    "def _prepare_trend_chart": "def prepare_trend_chart",
    "def _fetch_analytics_period_kpis": "def fetch_analytics_period_kpis",
    "def _fetch_analytics_intake_trend": "def fetch_analytics_intake_trend",
    "def _fetch_analytics_outcome_trend": "def fetch_analytics_outcome_trend",
    "def _fetch_analytics_fraud_trend": "def fetch_analytics_fraud_trend",
    "def _fetch_analytics_distribution": "def fetch_analytics_distribution",
    "def _fetch_analytics_pipeline_distribution": "def fetch_analytics_pipeline_distribution",
    "def _fetch_analytics_officer_workload": "def fetch_analytics_officer_workload",
    "def _fetch_analytics_backlog_snapshot": "def fetch_analytics_backlog_snapshot",
    "def _fetch_analytics_activity_summary": "def fetch_analytics_activity_summary",
    "def _analytics_insights": "def analytics_insights",
    "def _analytics_range_query": "def analytics_range_query",
    "def _fetch_pipeline_backlog": "def fetch_pipeline_backlog",
    "_analytics_datetime_clause": "analytics_datetime_clause",
    "def _parse_analytics_range": "def parse_analytics_range",
})
header = """from datetime import date, timedelta

from constants.analytics import ANALYTICS_MAX_TREND_POINTS, ANALYTICS_OFFICER_LIMIT
from constants.workflow import (
    APPLICATION_RISK_LEVELS,
    APPLICATION_STATUSES,
    KPI_ACTIVE_PIPELINE_STATUSES,
    KPI_APPROVED_STATUSES,
    KPI_HIGH_RISK_LEVELS,
    KPI_REJECTED_STATUS,
)
from repositories.applications import fetch_pipeline_backlog
from utils.time_range import analytics_datetime_clause, parse_analytics_range"""
(ROOT / "services/analytics.py").write_text(header + "\n\n" + body, encoding="utf-8")
print("services/analytics.py")

# services/reporting.py
body = g(1756, 1871)
body = subs(body, {
    "def _report_executive_summary": "def report_executive_summary",
    "def _build_reports_page_data": "def build_reports_page_data",
    "def _report_export_urls": "def report_export_urls",
    "_fetch_": "fetch_",
    "_fetch_governance": "fetch_governance",
})
# fix double fetch_ on governance
body = body.replace("fetch_governance_audit_summary", "fetch_governance_audit_summary")
header = """from flask import url_for

from constants.analytics import ANALYTICS_TIME_RANGES
from constants.workflow import APPLICATION_RISK_LEVELS, APPLICATION_STATUSES
from repositories.applications import (
    fetch_executive_kpis,
    fetch_fraud_review_summary,
    fetch_risk_distribution,
    fetch_status_distribution,
)
from repositories.audit import fetch_governance_audit_summary
from services.analytics import (
    fetch_analytics_activity_summary,
    fetch_analytics_backlog_snapshot,
    fetch_analytics_distribution,
    fetch_analytics_officer_workload,
    fetch_analytics_period_kpis,
    fetch_analytics_pipeline_distribution,
)"""
(ROOT / "services/reporting.py").write_text(header + "\n\n" + body, encoding="utf-8")
print("services/reporting.py")

# services/intake.py
(ROOT / "services/intake.py").write_text(
    "from constants.app import ALLOWED_PRODUCTS, EMAIL_PATTERN\n\n" + subs(g(262, 286), {"def _is_valid_application_form": "def is_valid_application_form"}),
    encoding="utf-8",
)
print("services/intake.py")

# services/overview.py
(ROOT / "services/overview.py").write_text(
    "from flask import url_for\n\n"
    + subs(g(1247, 1257), {"def _overview_drilldown_links": "def overview_drilldown_links"}),
    encoding="utf-8",
)
print("services/overview.py")
