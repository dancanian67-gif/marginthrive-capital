from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
lines = (ROOT / "app.py").read_text(encoding="utf-8").splitlines()
body = "\n".join(lines[2247:2735]) + "\n"

replacements = [
    ("@app.route", "@bp.route"),
    ("@require_admin_auth", "@require_admin_auth"),
    ("_get_db_connection()", "get_db_connection()"),
    ("_parse_analytics_range", "parse_analytics_range"),
    ("_fetch_executive_kpis", "fetch_executive_kpis"),
    ("_fetch_status_distribution", "fetch_status_distribution"),
    ("_fetch_risk_distribution", "fetch_risk_distribution"),
    ("_fetch_pipeline_backlog", "fetch_pipeline_backlog"),
    ("_fetch_officer_workload", "fetch_officer_workload"),
    ("_fetch_recent_applications", "fetch_recent_applications"),
    ("_fetch_attention_applications", "fetch_attention_applications"),
    ("_overview_drilldown_links", "overview_drilldown_links"),
    ("_fetch_analytics_period_kpis", "fetch_analytics_period_kpis"),
    ("_fetch_analytics_intake_trend", "fetch_analytics_intake_trend"),
    ("_fetch_analytics_fraud_trend", "fetch_analytics_fraud_trend"),
    ("_fetch_analytics_outcome_trend", "fetch_analytics_outcome_trend"),
    ("_fetch_analytics_distribution", "fetch_analytics_distribution"),
    ("_fetch_analytics_pipeline_distribution", "fetch_analytics_pipeline_distribution"),
    ("_fetch_analytics_officer_workload", "fetch_analytics_officer_workload"),
    ("_fetch_analytics_backlog_snapshot", "fetch_analytics_backlog_snapshot"),
    ("_fetch_analytics_activity_summary", "fetch_analytics_activity_summary"),
    ("_analytics_insights", "analytics_insights"),
    ("_report_export_urls", "report_export_urls"),
    ("_build_reports_page_data", "build_reports_page_data"),
    ("_parse_admin_list_filters", "parse_admin_list_filters"),
    ("_build_applications_where", "build_applications_where"),
    ("_fetch_application_kpis", "fetch_application_kpis"),
    ("_fetch_distinct_officers", "fetch_distinct_officers"),
    ("_filters_to_query_params", "filters_to_query_params"),
    ("_filters_have_constraints", "filters_have_constraints"),
    ("_active_filter_chips", "active_filter_chips"),
    ("_fetch_application", "fetch_application"),
    ("_fetch_workflow_history_rows", "fetch_workflow_history_rows"),
    ("_fetch_registered_officers", "fetch_registered_officers"),
    ("_group_workflow_history_batches", "group_workflow_history_batches"),
    ("_ensure_session_csrf_token", "ensure_session_csrf_token"),
    ("_next_pipeline_status", "next_pipeline_status"),
    ("_application_needs_attention", "application_needs_attention"),
    ("_get_request_actor", "get_request_actor"),
    ("_is_risky_status_transition_warning", "is_risky_status_transition_warning"),
    ("_validate_csrf", "validate_csrf"),
    ("_apply_workflow_quick_action", "apply_workflow_quick_action"),
    ("_validate_workflow_form", "validate_workflow_form"),
    ("_resolve_officer_name", "resolve_officer_name"),
    ("_workflow_snapshot_from_row", "workflow_snapshot_from_row"),
    ("_workflow_snapshot_from_workflow", "workflow_snapshot_from_workflow"),
    ("_requires_audit_context", "requires_audit_context"),
    ("_validate_audit_context", "validate_audit_context"),
    ("_persist_workflow_update", "persist_workflow_update"),
    ("_fetch_applications_for_export", "fetch_applications_for_export"),
    ("_fetch_audit_history_for_export", "fetch_audit_history_for_export"),
    ("_make_csv_response", "make_csv_response"),
    ("_make_sectioned_csv_response", "make_sectioned_csv_response"),
    ("_distribution_export_rows", "distribution_export_rows"),
    ("_safe_return_url", "safe_return_url"),
]
for o, n in replacements:
    body = body.replace(o, n)

header = '''from flask import Blueprint, Response, flash, g, redirect, render_template, request, url_for

from constants.analytics import ANALYTICS_TIME_RANGES
from constants.reporting import (
    APPLICATION_EXPORT_COLUMNS,
    AUDIT_EXPORT_COLUMNS,
    REPORT_EXPORT_TYPES,
)
from constants.workflow import (
    ADMIN_FILTER_PRESETS,
    ADMIN_PAGE_SIZE,
    APPLICATION_RISK_LEVELS,
    APPLICATION_STATUSES,
    APPLICATION_SUB_STATUSES,
    KPI_ACTIVE_PIPELINE_STATUSES,
)
from repositories.applications import (
    fetch_application,
    fetch_application_kpis,
    fetch_applications_for_export,
    fetch_attention_applications,
    fetch_executive_kpis,
    fetch_officer_workload,
    fetch_pipeline_backlog,
    fetch_recent_applications,
    fetch_risk_distribution,
    fetch_status_distribution,
)
from repositories.audit import fetch_audit_history_for_export, fetch_workflow_history_rows
from repositories.database import get_db_connection
from repositories.officers import fetch_registered_officers, resolve_officer_name
from services.analytics import (
    analytics_insights,
    fetch_analytics_activity_summary,
    fetch_analytics_backlog_snapshot,
    fetch_analytics_distribution,
    fetch_analytics_fraud_trend,
    fetch_analytics_intake_trend,
    fetch_analytics_officer_workload,
    fetch_analytics_outcome_trend,
    fetch_analytics_period_kpis,
    fetch_analytics_pipeline_distribution,
)
from services.audit import (
    group_workflow_history_batches,
    is_risky_status_transition_warning,
    persist_workflow_update,
    requires_audit_context,
    validate_audit_context,
    workflow_snapshot_from_row,
    workflow_snapshot_from_workflow,
)
from services.filters import (
    active_filter_chips,
    build_applications_where,
    filters_have_constraints,
    filters_to_query_params,
    parse_admin_list_filters,
    safe_return_url,
)
from services.overview import overview_drilldown_links
from services.reporting import build_reports_page_data, report_export_urls
from services.workflow import (
    apply_workflow_quick_action,
    application_needs_attention,
    next_pipeline_status,
    validate_workflow_form,
)
from utils.auth import get_request_actor, require_admin_auth
from utils.csv_export import distribution_export_rows, make_csv_response, make_sectioned_csv_response
from utils.csrf import ensure_session_csrf_token, validate_csrf
from utils.time_range import parse_analytics_range

bp = Blueprint("admin", __name__)

'''

(ROOT / "routes/admin.py").write_text(header + body, encoding="utf-8")
print("routes/admin.py written")
