

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
        "portfolio",
    }
)

APPLICATION_EXPORT_COLUMNS = (
    ("id", "id"),
    ("business_name", "business_name"),
    ("owner_name", "owner_name"),
    ("email", "email"),
    ("phone_number", "phone_number"),
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
    ("loan_lifecycle_status", "loan_lifecycle_status"),
    ("loan_account_number", "loan_account_number"),
    ("issued_amount", "issued_amount"),
    ("outstanding_balance", "outstanding_balance"),
    ("repayment_progress", "repayment_progress"),
    ("issue_date", "issue_date"),
    ("due_date", "due_date"),
    ("installment_amount", "installment_amount"),
    ("repayment_frequency", "repayment_frequency"),
    ("repayment_risk_level", "repayment_risk_level"),
    ("last_payment_at", "last_payment_at"),
    ("created_at", "created_at"),
    ("updated_at", "updated_at"),
)

REPAYMENT_EXPORT_COLUMNS = (
    ("id", "id"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("loan_account_number", "loan_account_number"),
    ("payment_date", "payment_date"),
    ("payment_amount", "payment_amount"),
    ("balance_before", "balance_before"),
    ("balance_after", "balance_after"),
    ("repayment_notes", "repayment_notes"),
    ("actor", "actor"),
    ("created_at", "created_at"),
)

COLLECTIONS_DELINQUENT_EXPORT_COLUMNS = (
    ("id", "id"),
    ("business_name", "business_name"),
    ("owner_name", "owner_name"),
    ("loan_account_number", "loan_account_number"),
    ("loan_lifecycle_status", "loan_lifecycle_status"),
    ("outstanding_balance", "outstanding_balance"),
    ("due_date", "due_date"),
    ("days_overdue", "days_overdue"),
    ("delinquency_bucket", "delinquency_bucket"),
    ("repayment_risk_level", "repayment_risk_level"),
    ("collections_status", "collections_status"),
    ("collections_priority", "collections_priority"),
    ("collections_assigned_to", "collections_assigned_to"),
    ("collections_risk_level", "collections_risk_level"),
    ("collections_next_follow_up", "collections_next_follow_up"),
    ("collections_last_contact_at", "collections_last_contact_at"),
)

COLLECTIONS_ACTIVITY_EXPORT_COLUMNS = (
    ("id", "id"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("loan_account_number", "loan_account_number"),
    ("collections_status", "collections_status"),
    ("collections_priority", "collections_priority"),
    ("collections_assigned_to", "collections_assigned_to"),
    ("collections_risk_level", "collections_risk_level"),
    ("action_type", "action_type"),
    ("actor", "actor"),
    ("context_notes", "context_notes"),
    ("created_at", "created_at"),
)

COLLECTIONS_WORKLOAD_EXPORT_COLUMNS = (
    ("officer", "officer"),
    ("case_count", "case_count"),
    ("exposure", "exposure"),
    ("high_priority_cases", "high_priority_cases"),
)

COLLECTIONS_RECOVERY_SUMMARY_EXPORT_COLUMNS = (
    ("id", "id"),
    ("business_name", "business_name"),
    ("loan_account_number", "loan_account_number"),
    ("collections_status", "collections_status"),
    ("collections_assigned_to", "collections_assigned_to"),
    ("days_overdue", "days_overdue"),
    ("outstanding_balance", "outstanding_balance"),
    ("intelligence_score", "intelligence_score"),
    ("intelligence_tier", "intelligence_tier"),
)

COLLECTIONS_ESCALATION_REPORT_COLUMNS = (
    ("id", "id"),
    ("business_name", "business_name"),
    ("loan_account_number", "loan_account_number"),
    ("collections_status", "collections_status"),
    ("collections_priority", "collections_priority"),
    ("collections_assigned_to", "collections_assigned_to"),
    ("collections_risk_level", "collections_risk_level"),
    ("days_overdue", "days_overdue"),
    ("outstanding_balance", "outstanding_balance"),
    ("flagged_fraud", "flagged_fraud"),
)

COLLECTIONS_OFFICER_RECOVERY_EXPORT_COLUMNS = (
    ("officer", "officer"),
    ("active_cases", "active_cases"),
    ("resolved_cases", "resolved_cases"),
    ("escalated_cases", "escalated_cases"),
    ("exposure", "exposure"),
    ("recovery_rate_pct", "recovery_rate_pct"),
)

COLLECTIONS_EXPOSURE_EXPORT_COLUMNS = (
    ("bucket", "bucket"),
    ("label", "label"),
    ("count", "count"),
    ("exposure", "exposure"),
    ("share", "share"),
)

COLLECTIONS_OUTCOME_DISTRIBUTION_EXPORT_COLUMNS = COLLECTIONS_EXPOSURE_EXPORT_COLUMNS

PROMISES_ACTIVE_EXPORT_COLUMNS = (
    ("id", "id"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("loan_account_number", "loan_account_number"),
    ("promise_amount", "promise_amount"),
    ("promise_date", "promise_date"),
    ("promise_status", "promise_status"),
    ("commitment_notes", "commitment_notes"),
    ("created_by", "created_by"),
    ("created_at", "created_at"),
)

PROMISES_BROKEN_EXPORT_COLUMNS = (
    ("id", "id"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("loan_account_number", "loan_account_number"),
    ("promise_amount", "promise_amount"),
    ("promise_date", "promise_date"),
    ("created_by", "created_by"),
    ("broken_at", "broken_at"),
    ("commitment_notes", "commitment_notes"),
)

PROMISES_OVERDUE_EXPORT_COLUMNS = (
    ("id", "id"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("loan_account_number", "loan_account_number"),
    ("promise_amount", "promise_amount"),
    ("promise_date", "promise_date"),
    ("created_by", "created_by"),
    ("days_overdue", "days_overdue"),
    ("commitment_notes", "commitment_notes"),
)

PROMISES_OFFICER_PERFORMANCE_EXPORT_COLUMNS = (
    ("officer", "officer"),
    ("total_commitments", "total_commitments"),
    ("fulfilled", "fulfilled"),
    ("broken", "broken"),
    ("active", "active"),
    ("fulfillment_rate_pct", "fulfillment_rate_pct"),
)

PROMISES_REPAYMENT_CONVERSION_EXPORT_COLUMNS = (
    ("promise_id", "promise_id"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("promise_amount", "promise_amount"),
    ("promise_date", "promise_date"),
    ("promise_status", "promise_status"),
    ("fulfilled_at", "fulfilled_at"),
    ("repayments_after_promise", "repayments_after_promise"),
)

NOTIFICATIONS_ALERTS_EXPORT_COLUMNS = (
    ("id", "id"),
    ("event_category", "event_category"),
    ("severity", "severity"),
    ("title", "title"),
    ("message", "message"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("governance_tag", "governance_tag"),
    ("is_acknowledged", "is_acknowledged"),
    ("acknowledged_at", "acknowledged_at"),
    ("acknowledged_by", "acknowledged_by"),
    ("created_at", "created_at"),
)

NOTIFICATIONS_UNRESOLVED_EXPORT_COLUMNS = (
    ("id", "id"),
    ("event_category", "event_category"),
    ("severity", "severity"),
    ("title", "title"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("governance_tag", "governance_tag"),
    ("created_at", "created_at"),
)

NOTIFICATIONS_GOVERNANCE_EXPORT_COLUMNS = (
    ("id", "id"),
    ("event_category", "event_category"),
    ("severity", "severity"),
    ("title", "title"),
    ("governance_tag", "governance_tag"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("is_acknowledged", "is_acknowledged"),
    ("created_at", "created_at"),
)

NOTIFICATIONS_ACK_METRICS_EXPORT_COLUMNS = (
    ("operator_scope", "operator_scope"),
    ("total_notifications", "total_notifications"),
    ("acknowledged", "acknowledged"),
    ("unresolved", "unresolved"),
    ("critical_unresolved", "critical_unresolved"),
    ("acknowledgement_rate_pct", "acknowledgement_rate_pct"),
)

NOTIFICATIONS_CRITICAL_EVENTS_EXPORT_COLUMNS = (
    ("id", "id"),
    ("event_category", "event_category"),
    ("severity", "severity"),
    ("title", "title"),
    ("application_id", "application_id"),
    ("business_name", "business_name"),
    ("actor", "actor"),
    ("governance_tag", "governance_tag"),
    ("created_at", "created_at"),
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
