"""Governance tagging and export classification (Phase E3)."""

# Structured tags appended to audit context_notes (workflow_history remains append-only)
GOV_TAG_FRAUD_OVERRIDE = "governance:fraud_override"
GOV_TAG_REPAYMENT_RECORD = "governance:repayment_recorded"
GOV_TAG_LOAN_CLOSURE = "governance:manual_loan_closure"
GOV_TAG_LOAN_DISTRESS = "governance:loan_distress_status"
GOV_TAG_UNDERWRITING_ESCALATION = "governance:underwriting_escalation"
GOV_TAG_UNDERWRITING_REJECTION = "governance:underwriting_rejection"
GOV_TAG_OPERATOR_DEACTIVATED = "governance:operator_deactivated"
GOV_TAG_HIGH_RISK_OVERRIDE = "governance:high_risk_workflow_override"
GOV_TAG_SENSITIVE_EXPORT = "governance:sensitive_export"
GOV_TAG_COLLECTIONS_LEGAL = "governance:collections_legal_escalation"
GOV_TAG_COLLECTIONS_WRITEOFF = "governance:collections_writeoff_recommendation"
GOV_TAG_COLLECTIONS_ESCALATION = "governance:collections_escalation"
GOV_TAG_COLLECTIONS_CLOSURE = "governance:collections_recovery_closure"
GOV_TAG_COLLECTIONS_DISPUTE = "governance:collections_dispute_escalation"
GOV_TAG_COLLECTIONS_FRAUD_RECOVERY = "governance:collections_fraud_recovery"
GOV_TAG_PROMISE_CREATED = "governance:collections_promise_created"
GOV_TAG_PROMISE_BROKEN = "governance:collections_promise_broken"
GOV_TAG_PROMISE_FULFILLED = "governance:collections_promise_fulfilled"
GOV_TAG_PROMISE_CANCELLED = "governance:collections_promise_cancelled"
GOV_TAG_NOTIFICATION_PERMISSION_DENIED = "governance:permission_denied_alert"
GOV_TAG_NOTIFICATION_GOVERNANCE = "governance:operational_alert"

EXPORT_SENSITIVITY_LEVELS = ("standard", "elevated", "governance")

EXPORT_TYPE_METADATA: dict[str, dict] = {
    "applications": {"sensitivity": "standard", "governance_tag": None},
    "audit": {"sensitivity": "governance", "governance_tag": GOV_TAG_SENSITIVE_EXPORT},
    "repayments": {"sensitivity": "governance", "governance_tag": GOV_TAG_SENSITIVE_EXPORT},
    "report_pipeline": {"sensitivity": "standard", "governance_tag": None},
    "report_risk": {"sensitivity": "elevated", "governance_tag": None},
    "report_outcomes": {"sensitivity": "standard", "governance_tag": None},
    "report_fraud": {"sensitivity": "governance", "governance_tag": GOV_TAG_SENSITIVE_EXPORT},
    "report_officers": {"sensitivity": "standard", "governance_tag": None},
    "report_backlog": {"sensitivity": "standard", "governance_tag": None},
    "report_operational": {"sensitivity": "standard", "governance_tag": None},
    "report_portfolio": {"sensitivity": "elevated", "governance_tag": None},
    "collections_delinquent": {"sensitivity": "governance", "governance_tag": GOV_TAG_SENSITIVE_EXPORT},
    "collections_activity": {"sensitivity": "governance", "governance_tag": GOV_TAG_SENSITIVE_EXPORT},
    "collections_workload": {"sensitivity": "elevated", "governance_tag": None},
    "collections_exposure": {"sensitivity": "elevated", "governance_tag": None},
    "collections_recovery_summary": {"sensitivity": "governance", "governance_tag": GOV_TAG_SENSITIVE_EXPORT},
    "collections_escalation_report": {"sensitivity": "governance", "governance_tag": GOV_TAG_SENSITIVE_EXPORT},
    "collections_officer_recovery": {"sensitivity": "elevated", "governance_tag": None},
    "collections_aging_movement": {"sensitivity": "elevated", "governance_tag": None},
    "collections_outcome_distribution": {"sensitivity": "elevated", "governance_tag": None},
    "promises_active": {"sensitivity": "elevated", "governance_tag": None},
    "promises_broken": {"sensitivity": "governance", "governance_tag": GOV_TAG_SENSITIVE_EXPORT},
    "promises_officer_performance": {"sensitivity": "standard", "governance_tag": None},
    "promises_repayment_conversion": {"sensitivity": "elevated", "governance_tag": None},
    "promises_overdue": {"sensitivity": "elevated", "governance_tag": None},
    "notifications_alerts": {"sensitivity": "elevated", "governance_tag": None},
    "notifications_unresolved": {"sensitivity": "elevated", "governance_tag": None},
    "notifications_governance": {"sensitivity": "governance", "governance_tag": GOV_TAG_SENSITIVE_EXPORT},
    "notifications_ack_metrics": {"sensitivity": "standard", "governance_tag": None},
    "notifications_critical_events": {"sensitivity": "governance", "governance_tag": GOV_TAG_SENSITIVE_EXPORT},
}

GOVERNANCE_DENIED_REPEAT_THRESHOLD = 3
GOVERNANCE_DENIED_WINDOW_SECONDS = 300
