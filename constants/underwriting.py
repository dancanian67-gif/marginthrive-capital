"""Underwriting and financing decision constants (Phase D2)."""

UNDERWRITING_STATUSES = (
    "pending_review",
    "in_review",
    "pending_clarification",
    "escalated_review",
    "approved",
    "conditionally_approved",
    "rejected",
)

UNDERWRITING_STATUS_LABELS = {
    "pending_review": "Pending review",
    "in_review": "In review",
    "pending_clarification": "Pending clarification",
    "escalated_review": "Escalated review",
    "approved": "Approved",
    "conditionally_approved": "Conditionally approved",
    "rejected": "Rejected",
}

DEFAULT_UNDERWRITING_STATUS = "pending_review"

UNDERWRITING_ASSESSMENT_RATINGS = (
    "not_assessed",
    "satisfactory",
    "acceptable_with_conditions",
    "concerns",
    "insufficient",
)

UNDERWRITING_ASSESSMENT_LABELS = {
    "not_assessed": "Not assessed",
    "satisfactory": "Satisfactory",
    "acceptable_with_conditions": "Acceptable with conditions",
    "concerns": "Concerns identified",
    "insufficient": "Insufficient basis",
}

UNDERWRITING_ASSESSMENT_FIELDS = (
    "affordability_assessment",
    "repayment_confidence",
    "business_stability_review",
    "documentation_quality_review",
)

UNDERWRITING_ASSESSMENT_FIELD_LABELS = {
    "affordability_assessment": "Affordability assessment",
    "repayment_confidence": "Repayment confidence",
    "business_stability_review": "Business stability review",
    "documentation_quality_review": "Documentation quality review",
}

UNDERWRITING_DECISION_STATUSES = frozenset(
    {"approved", "conditionally_approved", "rejected", "pending_clarification", "escalated_review"}
)

UNDERWRITING_STATUSES_REQUIRING_RATIONALE = frozenset(
    {"approved", "conditionally_approved", "rejected", "pending_clarification", "escalated_review"}
)

UNDERWRITING_STATUSES_REQUIRING_ESCALATION_REASON = frozenset({"escalated_review"})

UNDERWRITING_CRITICAL_STATUSES = frozenset(
    {"rejected", "conditionally_approved", "escalated_review"}
)

MAX_UNDERWRITING_NOTES_LENGTH = 5000
MAX_DECISION_SUMMARY_LENGTH = 2000
MAX_DECISION_REASON_LENGTH = 2000
MAX_ESCALATION_REASON_LENGTH = 2000
MAX_OBSERVATION_LENGTH = 2000

UNDERWRITING_AUDIT_FIELDS = (
    "underwriting_status",
    "affordability_assessment",
    "repayment_confidence",
    "business_stability_review",
    "documentation_quality_review",
    "operational_risk_observations",
    "fraud_concern_observations",
    "underwriting_notes",
    "decision_summary",
    "decision_reason",
    "escalation_reason",
    "reviewed_by",
)

UNDERWRITING_FIELD_ACTION_TYPES = {
    "underwriting_status": "underwriting_status_change",
    "affordability_assessment": "underwriting_assessment_change",
    "repayment_confidence": "underwriting_assessment_change",
    "business_stability_review": "underwriting_assessment_change",
    "documentation_quality_review": "underwriting_assessment_change",
    "operational_risk_observations": "underwriting_observation_change",
    "fraud_concern_observations": "underwriting_observation_change",
    "underwriting_notes": "underwriting_notes_change",
    "decision_summary": "underwriting_decision_change",
    "decision_reason": "underwriting_decision_change",
    "escalation_reason": "underwriting_escalation_change",
    "reviewed_by": "underwriting_review_attribution",
}
