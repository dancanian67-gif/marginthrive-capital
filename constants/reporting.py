

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
    ("underwriting_status", "underwriting_status"),
    ("decision_summary", "decision_summary"),
    ("decision_reason", "decision_reason"),
    ("reviewed_by", "reviewed_by"),
    ("reviewed_at", "reviewed_at"),
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
