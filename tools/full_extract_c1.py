"""Full Phase C1 extraction from app.py into modules."""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEXT = (ROOT / "app.py").read_text(encoding="utf-8")
LINES = TEXT.splitlines()


def lines(start: int, end: int) -> str:
    return "\n".join(LINES[start - 1 : end]) + "\n"


def put(path: str, header: str, body: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"{header.rstrip()}\n\n{body.lstrip()}", encoding="utf-8")
    print("wrote", path)


def rename_funcs(body: str, mapping: dict[str, str]) -> str:
    for old, new in mapping.items():
        body = body.replace(f"def {old}(", f"def {new}(")
        body = body.replace(f"{old}(", f"{new}(")
    return body


DB_RENAME = {"_get_db_connection": "get_db_connection"}

# Fix officers file
officers_body = lines(478, 537)
officers_body = rename_funcs(officers_body, {
    "_init_officers_table": "init_officers_table",
    "_seed_officers_table": "seed_officers_table",
    "_ensure_officer_registered": "ensure_officer_registered",
    "_fetch_registered_officers": "fetch_registered_officers",
    "_resolve_officer_name": "resolve_officer_name",
    "_normalize_officer_name": "normalize_officer_name",
})
put(
    "repositories/officers.py",
    """from constants.workflow import MAX_ASSIGNED_OFFICER_LENGTH, OFFICER_NAME_PATTERN""",
    officers_body,
)

audit_repo = rename_funcs(lines(443, 505) + lines(867, 927) + lines(1674, 1736), DB_RENAME)
audit_repo = rename_funcs(audit_repo, {
    "_init_workflow_history_table": "init_workflow_history_table",
    "_fetch_workflow_history_rows": "fetch_workflow_history_rows",
    "_group_workflow_history_batches": "group_workflow_history_batches",
    "_fetch_audit_history_for_export": "fetch_audit_history_for_export",
    "_fetch_governance_audit_summary": "fetch_governance_audit_summary",
    "_history_event_summary": "history_event_summary",
})
put(
    "repositories/audit.py",
    "from repositories.database import get_db_connection",
    audit_repo,
)

audit_svc = rename_funcs(lines(550, 865), DB_RENAME)
audit_svc = rename_funcs(audit_svc, {
    "_workflow_snapshot_from_row": "workflow_snapshot_from_row",
    "_workflow_snapshot_from_workflow": "workflow_snapshot_from_workflow",
    "_workflow_snapshot_json": "workflow_snapshot_json",
    "_format_audit_field_value": "format_audit_field_value",
    "_diff_workflow_snapshots": "diff_workflow_snapshots",
    "_workflow_change_is_critical": "workflow_change_is_critical",
    "_requires_audit_context": "requires_audit_context",
    "_normalize_audit_context": "normalize_audit_context",
    "_validate_audit_context": "validate_audit_context",
    "_insert_workflow_history_entries": "insert_workflow_history_entries",
    "_persist_workflow_update": "persist_workflow_update",
    "_log_application_created": "log_application_created",
    "_ensure_officer_registered": "ensure_officer_registered",
})
put(
    "services/audit.py",
    """import json
import secrets

from constants.audit import (
    PUBLIC_INTAKE_ACTOR,
    QUICK_ACTION_AUDIT_TYPES,
    SENSITIVE_AUDIT_STATUSES,
    WORKFLOW_AUDIT_FIELDS,
    WORKFLOW_FIELD_ACTION_TYPES,
)
from constants.workflow import (
    DEFAULT_APPLICATION_STATUS,
    DEFAULT_RISK_LEVEL,
    KPI_APPROVED_STATUSES,
    KPI_OPS_REVIEW_SUB_STATUS,
    KPI_REJECTED_STATUS,
)
from repositories.audit import insert_workflow_history_entries
from repositories.database import get_db_connection
from repositories.officers import ensure_officer_registered
from services.workflow import is_allowed_status_transition""",
    audit_svc,
)

# Fix circular import: is_risky in audit service imports workflow - move is_risky to workflow
# For now keep is_risky in audit body - it calls is_allowed from workflow at runtime

filters_body = rename_funcs(lines(930, 1042) + lines(2112, 2185), DB_RENAME)
filters_body = rename_funcs(filters_body, {
    "_parse_admin_list_filters": "parse_admin_list_filters",
    "_build_applications_where": "build_applications_where",
    "_filters_to_query_params": "filters_to_query_params",
    "_filters_have_constraints": "filters_have_constraints",
    "_active_filter_chips": "active_filter_chips",
    "_safe_return_url": "safe_return_url",
})
put(
    "services/filters.py",
    """from flask import url_for

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
)""",
    filters_body,
)

apps_body = rename_funcs(lines(1045, 1244) + lines(1642, 1671) + lines(1739, 1754) + lines(1948, 1954), DB_RENAME)
apps_body = rename_funcs(apps_body, {
    "_fetch_executive_kpis": "fetch_executive_kpis",
    "_fetch_application_kpis": "fetch_application_kpis",
    "_fetch_status_distribution": "fetch_status_distribution",
    "_fetch_risk_distribution": "fetch_risk_distribution",
    "_fetch_pipeline_backlog": "fetch_pipeline_backlog",
    "_fetch_officer_workload": "fetch_officer_workload",
    "_fetch_recent_applications": "fetch_recent_applications",
    "_fetch_attention_applications": "fetch_attention_applications",
    "_fetch_application": "fetch_application",
    "_fetch_applications_for_export": "fetch_applications_for_export",
    "_fetch_fraud_review_summary": "fetch_fraud_review_summary",
})
put(
    "repositories/applications.py",
    """from constants.reporting import REPORT_EXPORT_MAX_ROWS
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
from repositories.database import get_db_connection""",
    apps_body,
)

analytics_body = rename_funcs(lines(1260, 1261) + lines(1264, 1597), DB_RENAME)  # skip duplicate fetch_distinct
analytics_body = rename_funcs(analytics_body, {
    "_parse_analytics_range": "parse_analytics_range",
    "_analytics_datetime_clause": "analytics_datetime_clause",
    "_analytics_range_span_days": "analytics_range_span_days",
    "_add_distribution_shares": "add_distribution_shares",
    "_fill_daily_trend": "fill_daily_trend",
    "_prepare_trend_chart": "prepare_trend_chart",
    "_fetch_analytics_period_kpis": "fetch_analytics_period_kpis",
    "_fetch_analytics_intake_trend": "fetch_analytics_intake_trend",
    "_fetch_analytics_outcome_trend": "fetch_analytics_outcome_trend",
    "_fetch_analytics_fraud_trend": "fetch_analytics_fraud_trend",
    "_fetch_analytics_distribution": "fetch_analytics_distribution",
    "_fetch_analytics_pipeline_distribution": "fetch_analytics_pipeline_distribution",
    "_fetch_analytics_officer_workload": "fetch_analytics_officer_workload",
    "_fetch_analytics_backlog_snapshot": "fetch_analytics_backlog_snapshot",
    "_fetch_analytics_activity_summary": "fetch_analytics_activity_summary",
    "_analytics_insights": "analytics_insights",
    "_analytics_range_query": "analytics_range_query",
    "_fetch_pipeline_backlog": "fetch_pipeline_backlog",
})
put(
    "services/analytics.py",
    """from datetime import date, timedelta

from constants.analytics import (
    ANALYTICS_MAX_TREND_POINTS,
    ANALYTICS_OFFICER_LIMIT,
    ANALYTICS_TIME_RANGES,
    DEFAULT_ANALYTICS_RANGE,
)
from constants.workflow import (
    APPLICATION_RISK_LEVELS,
    APPLICATION_STATUSES,
    KPI_ACTIVE_PIPELINE_STATUSES,
    KPI_APPROVED_STATUSES,
    KPI_HIGH_RISK_LEVELS,
    KPI_REJECTED_STATUS,
)
from repositories.applications import fetch_pipeline_backlog""",
    analytics_body,
)

report_body = rename_funcs(lines(1756, 1871), DB_RENAME)
report_body = rename_funcs(report_body, {
    "_report_executive_summary": "report_executive_summary",
    "_build_reports_page_data": "build_reports_page_data",
    "_report_export_urls": "report_export_urls",
    "_fetch_executive_kpis": "fetch_executive_kpis",
    "_fetch_analytics_period_kpis": "fetch_analytics_period_kpis",
    "_fetch_analytics_distribution": "fetch_analytics_distribution",
    "_fetch_analytics_pipeline_distribution": "fetch_analytics_pipeline_distribution",
    "_fetch_analytics_officer_workload": "fetch_analytics_officer_workload",
    "_fetch_analytics_backlog_snapshot": "fetch_analytics_backlog_snapshot",
    "_fetch_analytics_activity_summary": "fetch_analytics_activity_summary",
    "_fetch_governance_audit_summary": "fetch_governance_audit_summary",
    "_fetch_fraud_review_summary": "fetch_fraud_review_summary",
    "_fetch_status_distribution": "fetch_status_distribution",
    "_fetch_risk_distribution": "fetch_risk_distribution",
})
put(
    "services/reporting.py",
    """from flask import url_for

from constants.analytics import ANALYTICS_TIME_RANGES
from constants.workflow import APPLICATION_RISK_LEVELS, APPLICATION_STATUSES
from repositories.applications import (
    fetch_executive_kpis,
    fetch_fraud_review_summary,
    fetch_risk_distribution,
    fetch_status_distribution,
)
from services.analytics import (
    fetch_analytics_activity_summary,
    fetch_analytics_backlog_snapshot,
    fetch_analytics_distribution,
    fetch_analytics_officer_workload,
    fetch_analytics_period_kpis,
    fetch_analytics_pipeline_distribution,
)
from repositories.audit import fetch_governance_audit_summary""",
    report_body,
)

workflow_body = rename_funcs(lines(1957, 2109) + lines(2188, 2196), DB_RENAME)
workflow_body = rename_funcs(workflow_body, {
    "_normalize_sub_status": "normalize_sub_status",
    "_normalize_officer_name": "normalize_officer_name",
    "_parse_flagged_fraud": "parse_flagged_fraud",
    "_is_allowed_status_transition": "is_allowed_status_transition",
    "_is_risky_status_transition_warning": "is_risky_status_transition_warning",
    "_next_pipeline_status": "next_pipeline_status",
    "_workflow_row_signature": "workflow_row_signature",
    "_validate_workflow_form": "validate_workflow_form",
    "_apply_workflow_quick_action": "apply_workflow_quick_action",
    "_application_needs_attention": "application_needs_attention",
})
put(
    "services/workflow.py",
    """import sqlite3

from constants.audit import QUICK_ACTIONS_REQUIRING_AUDIT_NOTE
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
    MAX_ASSIGNED_OFFICER_LENGTH,
    OFFICER_NAME_PATTERN,
)""",
    workflow_body,
)

put("services/intake.py", "from constants.app import ALLOWED_PRODUCTS, EMAIL_PATTERN", rename_funcs(lines(262, 286), {}))

put("services/overview.py", "from flask import url_for", rename_funcs(lines(1247, 1257), {"_overview_drilldown_links": "overview_drilldown_links"}))

put(
    "repositories/officers.py",
    (ROOT / "repositories/officers.py").read_text(encoding="utf-8"),
    1,
    1,
)  # noop placeholder

print("done batch 2")
