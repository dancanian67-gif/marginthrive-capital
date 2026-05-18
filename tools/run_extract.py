"""Run Phase C1 code extraction from app.py."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L = (ROOT / "app.py").read_text(encoding="utf-8").splitlines()


def g(a, b):
    return "\n".join(L[a - 1 : b]) + "\n"


def w(rel, header, a, b, subs=None):
    body = g(a, b)
    if subs:
        for o, n in subs.items():
            body = body.replace(o, n)
    (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / rel).write_text(f"{header}\n\n{body}", encoding="utf-8")
    print(rel)


SUB = {"_get_db_connection()": "get_db_connection()", "def _get_db_connection": "def get_db_connection"}

# repositories/audit.py
w("repositories/audit.py", "", 443, 505, {
    "def _init_workflow_history_table": "def init_workflow_history_table",
})
body = g(867, 927) + g(1674, 1736)
for o, n in {
    "def _fetch_workflow_history_rows": "def fetch_workflow_history_rows",
    "def _group_workflow_history_batches": "def group_workflow_history_batches",
    "def _fetch_audit_history_for_export": "def fetch_audit_history_for_export",
    "def _fetch_governance_audit_summary": "def fetch_governance_audit_summary",
    "_history_event_summary": "history_event_summary",
}.items():
    body = body.replace(o, n)
(ROOT / "repositories/audit.py").write_text(
    (ROOT / "repositories/audit.py").read_text(encoding="utf-8") + "\n" + body, encoding="utf-8"
)

# services/audit.py  
audit_header = '''import json
import secrets

from constants.audit import (
    PUBLIC_INTAKE_ACTOR,
    QUICK_ACTION_AUDIT_TYPES,
    WORKFLOW_AUDIT_FIELDS,
    WORKFLOW_FIELD_ACTION_TYPES,
)
from constants.workflow import (
    APPLICATION_STATUSES,
    DEFAULT_APPLICATION_STATUS,
    DEFAULT_RISK_LEVEL,
    KPI_APPROVED_STATUSES,
    KPI_OPS_REVIEW_SUB_STATUS,
    KPI_REJECTED_STATUS,
    SENSITIVE_AUDIT_STATUSES,
)
from repositories.database import get_db_connection
from repositories.officers import ensure_officer_registered
from services.workflow import is_allowed_status_transition
'''
audit_body = g(550, 865)
for o, n in {
    "def _workflow_snapshot_from_row": "def workflow_snapshot_from_row",
    "def _workflow_snapshot_from_workflow": "def workflow_snapshot_from_workflow",
    "def _workflow_snapshot_json": "def workflow_snapshot_json",
    "def _format_audit_field_value": "def format_audit_field_value",
    "def _diff_workflow_snapshots": "def diff_workflow_snapshots",
    "def _workflow_change_is_critical": "def workflow_change_is_critical",
    "def _is_risky_status_transition_warning": "def is_risky_status_transition_warning",
    "def _requires_audit_context": "def requires_audit_context",
    "def _normalize_audit_context": "def normalize_audit_context",
    "def _validate_audit_context": "def validate_audit_context",
    "def _history_event_summary": "def history_event_summary",
    "def _insert_workflow_history_entries": "def insert_workflow_history_entries",
    "def _persist_workflow_update": "def persist_workflow_update",
    "def _log_application_created": "def log_application_created",
    "_is_allowed_status_transition": "is_allowed_status_transition",
    "_ensure_officer_registered": "ensure_officer_registered",
}.items():
    audit_body = audit_body.replace(o, n)
w("services/audit.py", audit_header, 1, 1)
(ROOT / "services/audit.py").write_text(audit_header + "\n" + audit_body, encoding="utf-8")

# services/workflow.py
wf_header = '''import sqlite3

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
)
'''
wf_body = g(1964, 2109) + g(2188, 2196)
for o, n in {
    "def _normalize_sub_status": "def normalize_sub_status",
    "def _normalize_officer_name": "def normalize_officer_name",
    "def _parse_flagged_fraud": "def parse_flagged_fraud",
    "def _is_allowed_status_transition": "def is_allowed_status_transition",
    "def _next_pipeline_status": "def next_pipeline_status",
    "def _workflow_row_signature": "def workflow_row_signature",
    "def _validate_workflow_form": "def validate_workflow_form",
    "def _apply_workflow_quick_action": "def apply_workflow_quick_action",
    "def _application_needs_attention": "def application_needs_attention",
}.items():
    wf_body = wf_body.replace(o, n)
(ROOT / "services/workflow.py").write_text(wf_header + "\n" + wf_body, encoding="utf-8")
print("services/workflow.py")

# officers resolve
off_body = g(540, 548)
off_body = off_body.replace("def _resolve_officer_name", "def resolve_officer_name").replace(
    "_normalize_officer_name", "normalize_officer_name"
)
(ROOT / "repositories/officers.py").write_text(
    (ROOT / "repositories/officers.py").read_text(encoding="utf-8") + "\n" + off_body, encoding="utf-8"
)
# add normalize to officers
norm = g(1964, 1970).replace("def _normalize_officer_name", "def normalize_officer_name")
(ROOT / "repositories/officers.py").write_text(
    (ROOT / "repositories/officers.py").read_text(encoding="utf-8").split("def resolve_officer_name")[0]
    + norm
    + "\n\n"
    + "def resolve_officer_name"
    + "def resolve_officer_name".join(
        (ROOT / "repositories/officers.py").read_text(encoding="utf-8").split("def resolve_officer_name")[1:]
    ),
    encoding="utf-8",
)

print("extract pass complete")
