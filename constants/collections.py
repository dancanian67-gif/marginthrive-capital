"""Collections operations and delinquency constants (Phase F1)."""

from constants.portfolio import PORTFOLIO_AGING_BUCKETS, PORTFOLIO_AGING_LABELS

COLLECTIONS_STATUSES = (
    "not_in_collections",
    "queued",
    "in_contact",
    "promise_to_pay",
    "payment_plan",
    "escalated_review",
    "legal_escalation",
    "recovery_active",
    "resolved",
    "write_off_recommended",
)

COLLECTIONS_STATUS_LABELS = {
    "not_in_collections": "Not in collections",
    "queued": "Queued for collections",
    "in_contact": "In contact",
    "promise_to_pay": "Promise to pay",
    "payment_plan": "Payment plan active",
    "escalated_review": "Escalated review",
    "legal_escalation": "Legal escalation",
    "recovery_active": "Recovery active",
    "resolved": "Resolved",
    "write_off_recommended": "Write-off recommended",
}

DEFAULT_COLLECTIONS_STATUS = "not_in_collections"

COLLECTIONS_PRIORITIES = ("low", "normal", "high", "urgent")

COLLECTIONS_PRIORITY_LABELS = {
    "low": "Low",
    "normal": "Normal",
    "high": "High",
    "urgent": "Urgent",
}

DEFAULT_COLLECTIONS_PRIORITY = "normal"

COLLECTIONS_RISK_LEVELS = ("routine", "elevated", "critical", "legal")

COLLECTIONS_RISK_LABELS = {
    "routine": "Routine",
    "elevated": "Elevated",
    "critical": "Critical",
    "legal": "Legal / recovery",
}

DEFAULT_COLLECTIONS_RISK_LEVEL = "routine"

COLLECTIONS_CRITICAL_STATUSES = frozenset(
    {"escalated_review", "legal_escalation", "write_off_recommended"}
)

COLLECTIONS_SENSITIVE_STATUSES = frozenset(
    {"legal_escalation", "write_off_recommended", "escalated_review"}
)

COLLECTIONS_AUDIT_FIELDS = (
    "collections_status",
    "collections_priority",
    "collections_assigned_to",
    "collections_last_contact_at",
    "collections_next_follow_up",
    "collections_notes_summary",
    "collections_risk_level",
)

COLLECTIONS_FIELD_ACTION_TYPES = {
    "collections_status": "collections_status_change",
    "collections_priority": "collections_priority_change",
    "collections_assigned_to": "collections_assignment",
    "collections_last_contact_at": "collections_contact_update",
    "collections_next_follow_up": "collections_follow_up_update",
    "collections_notes_summary": "collections_notes_update",
    "collections_risk_level": "collections_risk_change",
}

DELINQUENCY_BUCKETS = PORTFOLIO_AGING_BUCKETS
DELINQUENCY_BUCKET_LABELS = PORTFOLIO_AGING_LABELS

COLLECTIONS_PAGE_SIZE = 15
COLLECTIONS_HISTORY_LIMIT = 50
COLLECTIONS_QUEUE_LIMIT = 200
MAX_COLLECTIONS_NOTES_LENGTH = 5000
MAX_COLLECTIONS_ASSIGNED_LENGTH = 150

# Phase F2 — intelligence priority tiers (distinct from manual collections_priority field)
INTELLIGENCE_PRIORITY_TIERS = ("low", "moderate", "elevated", "critical")

INTELLIGENCE_PRIORITY_LABELS = {
    "low": "Low intelligence priority",
    "moderate": "Moderate intelligence priority",
    "elevated": "Elevated intelligence priority",
    "critical": "Critical intelligence priority",
}

INTELLIGENCE_TIER_ORDER = {"critical": 4, "elevated": 3, "moderate": 2, "low": 1}

# Timeline event categories (F2)
TIMELINE_CATEGORY_CONTACT = "contact"
TIMELINE_CATEGORY_ESCALATION = "escalation"
TIMELINE_CATEGORY_REPAYMENT = "repayment"
TIMELINE_CATEGORY_PROMISE = "promise"
TIMELINE_CATEGORY_LEGAL = "legal_review"
TIMELINE_CATEGORY_WRITEOFF = "write_off_review"
TIMELINE_CATEGORY_GENERAL = "general"

TIMELINE_CATEGORY_LABELS = {
    TIMELINE_CATEGORY_CONTACT: "Contact",
    TIMELINE_CATEGORY_ESCALATION: "Escalation",
    TIMELINE_CATEGORY_REPAYMENT: "Repayment",
    TIMELINE_CATEGORY_PROMISE: "Promise to pay",
    TIMELINE_CATEGORY_LEGAL: "Legal review",
    TIMELINE_CATEGORY_WRITEOFF: "Write-off review",
    TIMELINE_CATEGORY_GENERAL: "Collections update",
}

STATUS_TO_TIMELINE_CATEGORY = {
    "in_contact": TIMELINE_CATEGORY_CONTACT,
    "promise_to_pay": TIMELINE_CATEGORY_PROMISE,
    "payment_plan": TIMELINE_CATEGORY_REPAYMENT,
    "escalated_review": TIMELINE_CATEGORY_ESCALATION,
    "legal_escalation": TIMELINE_CATEGORY_LEGAL,
    "write_off_recommended": TIMELINE_CATEGORY_WRITEOFF,
    "recovery_active": TIMELINE_CATEGORY_REPAYMENT,
    "resolved": TIMELINE_CATEGORY_GENERAL,
}

# F2 governance — sensitive recovery actions (context mandatory)
COLLECTIONS_GOVERNANCE_SENSITIVE_STATUSES = frozenset(
    {
        "legal_escalation",
        "write_off_recommended",
        "escalated_review",
        "resolved",
        "promise_to_pay",
    }
)

COLLECTIONS_STATUSES_REQUIRING_CONTEXT = COLLECTIONS_GOVERNANCE_SENSITIVE_STATUSES

COLLECTIONS_LIST_FILTER_KEYS = (
    "collections_status",
    "collections_priority",
    "collections_assigned_to",
    "collections_risk_level",
    "delinquency_bucket",
    "q",
    "page",
)
