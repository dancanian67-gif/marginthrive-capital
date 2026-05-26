"""Operational event and notification constants (Phase G1)."""

EVENT_SEVERITIES = ("info", "warning", "critical")
EVENT_SEVERITY_LABELS = {
    "info": "Info",
    "warning": "Warning",
    "critical": "Critical",
}

EVENT_CATEGORIES = (
    "workflow_transition",
    "underwriting_decision",
    "repayment_recorded",
    "collections_escalation",
    "broken_promise",
    "overdue_followup",
    "critical_risk",
    "governance_alert",
    "operator_action_required",
)

EVENT_CATEGORY_LABELS = {
    "workflow_transition": "Workflow transition",
    "underwriting_decision": "Underwriting decision",
    "repayment_recorded": "Repayment recorded",
    "collections_escalation": "Collections escalation",
    "broken_promise": "Broken promise",
    "overdue_followup": "Overdue follow-up",
    "critical_risk": "Critical risk",
    "governance_alert": "Governance alert",
    "operator_action_required": "Action required",
}

NOTIFICATION_FILTER_ALL = ""
NOTIFICATION_FILTER_UNREAD = "unread"
NOTIFICATION_FILTER_CRITICAL = "critical"
NOTIFICATION_FILTER_GOVERNANCE = "governance"

NOTIFICATION_FILTERS = (
    NOTIFICATION_FILTER_ALL,
    NOTIFICATION_FILTER_UNREAD,
    NOTIFICATION_FILTER_CRITICAL,
    NOTIFICATION_FILTER_GOVERNANCE,
)

NOTIFICATION_FILTER_LABELS = {
    NOTIFICATION_FILTER_ALL: "All notifications",
    NOTIFICATION_FILTER_UNREAD: "Unread only",
    NOTIFICATION_FILTER_CRITICAL: "Critical severity",
    NOTIFICATION_FILTER_GOVERNANCE: "Governance alerts",
}

NOTIFICATION_PAGE_SIZE = 25
NOTIFICATION_SUMMARY_LIMIT = 8

GOVERNANCE_EVENT_CATEGORIES = frozenset(
    {
        "governance_alert",
        "collections_escalation",
        "broken_promise",
        "critical_risk",
    }
)
