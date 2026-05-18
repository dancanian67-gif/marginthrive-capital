

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
