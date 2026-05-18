"""Build Phase C1 modules from app.py by relocating function groups."""
from __future__ import annotations

import pathlib
import re
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "app.py").read_text(encoding="utf-8")

# Parse top-level functions (simple regex; app.py uses flat functions)
FUNC_PATTERN = re.compile(
    r"^((?:@[^\n]+\n)*)def ([a-zA-Z_][a-zA-Z0-9_]*)\([^)]*\)(?: -> [^:]+)?:.*?(?=^(?:@|\ndef |if __name__))",
    re.MULTILINE | re.DOTALL,
)
funcs = {m.group(2): m.group(0) for m in FUNC_PATTERN.finditer(SRC + "\n")}

GROUPS: dict[str, list[str]] = {
    "utils/env.py": ["_is_development", "_get_bool_env"],
    "utils/csrf.py": ["_ensure_session_csrf_token", "_validate_csrf"],
    "utils/auth.py": [
        "_parse_basic_auth_credentials",
        "_check_admin_auth",
        "_get_request_actor",
        "require_admin_auth",
    ],
    "services/intake.py": ["_is_valid_application_form"],
    "repositories/database.py": [
        "_get_db_connection",
        "_applications_column_names",
        "_migrate_applications_table",
        "init_db",
        "_init_workflow_history_table",
        "_init_officers_table",
        "_seed_officers_table",
    ],
    "repositories/officers.py": [
        "_ensure_officer_registered",
        "_fetch_registered_officers",
        "_fetch_distinct_officers",
    ],
    "services/audit_repository.py": [
        "_fetch_workflow_history_rows",
        "_group_workflow_history_batches",
        "_fetch_audit_history_for_export",
        "_fetch_governance_audit_summary",
    ],
    "services/audit.py": [
        "_workflow_snapshot_from_row",
        "_workflow_snapshot_from_workflow",
        "_workflow_snapshot_json",
        "_format_audit_field_value",
        "_diff_workflow_snapshots",
        "_workflow_change_is_critical",
        "_requires_audit_context",
        "_normalize_audit_context",
        "_validate_audit_context",
        "_history_event_summary",
        "_insert_workflow_history_entries",
        "_persist_workflow_update",
        "_log_application_created",
    ],
    "services/filters.py": [
        "_parse_admin_list_filters",
        "_build_applications_where",
        "_filters_to_query_params",
        "_filters_have_constraints",
        "_active_filter_chips",
        "_safe_return_url",
    ],
    "repositories/applications.py": [
        "_fetch_executive_kpis",
        "_fetch_application_kpis",
        "_fetch_status_distribution",
        "_fetch_risk_distribution",
        "_fetch_pipeline_backlog",
        "_fetch_officer_workload",
        "_fetch_recent_applications",
        "_fetch_attention_applications",
        "_fetch_application",
        "_fetch_applications_for_export",
        "_fetch_fraud_review_summary",
    ],
    "services/analytics.py": [
        "_parse_analytics_range",
        "_analytics_datetime_clause",
        "_analytics_range_span_days",
        "_add_distribution_shares",
        "_fill_daily_trend",
        "_prepare_trend_chart",
        "_fetch_analytics_period_kpis",
        "_fetch_analytics_intake_trend",
        "_fetch_analytics_outcome_trend",
        "_fetch_analytics_fraud_trend",
        "_fetch_analytics_distribution",
        "_fetch_analytics_pipeline_distribution",
        "_fetch_analytics_officer_workload",
        "_fetch_analytics_backlog_snapshot",
        "_fetch_analytics_activity_summary",
        "_analytics_insights",
        "_analytics_range_query",
    ],
    "utils/csv_export.py": [
        "_make_csv_response",
        "_make_sectioned_csv_response",
        "_distribution_export_rows",
    ],
    "services/reporting.py": [
        "_report_executive_summary",
        "_build_reports_page_data",
        "_report_export_urls",
    ],
    "services/workflow.py": [
        "_resolve_officer_name",
        "_normalize_sub_status",
        "_normalize_officer_name",
        "_parse_flagged_fraud",
        "_is_allowed_status_transition",
        "_is_risky_status_transition_warning",
        "_next_pipeline_status",
        "_workflow_row_signature",
        "_validate_workflow_form",
        "_apply_workflow_quick_action",
        "_application_needs_attention",
    ],
    "services/overview.py": ["_overview_drilldown_links"],
}

HEADERS: dict[str, str] = {
    "utils/env.py": "import os",
    "utils/csrf.py": textwrap.dedent(
        """\
        import hmac
        import secrets

        from flask import session
        """
    ),
    "utils/auth.py": textwrap.dedent(
        """\
        import base64
        import hmac
        import os
        from functools import wraps

        from flask import Response, g, request
        """
    ),
    "services/intake.py": textwrap.dedent(
        """\
        from constants.app import ALLOWED_PRODUCTS, EMAIL_PATTERN
        """
    ),
    "repositories/database.py": textwrap.dedent(
        """\
        import sqlite3

        from constants.app import DATABASE_PATH
        from constants.schema import APPLICATIONS_SCHEMA_COLUMNS
        from constants.workflow import DEFAULT_APPLICATION_STATUS, DEFAULT_RISK_LEVEL
        from repositories.officers import seed_officers_table
        from services.audit_repository import init_workflow_history_table
        """
    ),
}

print("Found functions:", len(funcs))
for path, names in GROUPS.items():
    missing = [n for n in names if n not in funcs]
    if missing:
        print("MISSING in", path, missing)
