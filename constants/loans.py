"""Loan lifecycle, repayment, and collections constants (Phase D3)."""

LOAN_LIFECYCLE_STATUSES = (
    "not_issued",
    "active",
    "repaying",
    "overdue",
    "completed",
    "defaulted",
    "written_off",
)

LOAN_LIFECYCLE_STATUS_LABELS = {
    "not_issued": "Not issued",
    "active": "Active",
    "repaying": "Repaying",
    "overdue": "Overdue",
    "completed": "Completed",
    "defaulted": "Defaulted",
    "written_off": "Written off",
}

DEFAULT_LOAN_LIFECYCLE_STATUS = "not_issued"

ACTIVE_LOAN_LIFECYCLE_STATUSES = frozenset({"active", "repaying", "overdue"})

TERMINAL_LOAN_LIFECYCLE_STATUSES = frozenset({"completed", "defaulted", "written_off"})

SERVICING_LOAN_LIFECYCLE_STATUSES = frozenset({"active", "repaying", "overdue", "defaulted"})

LOAN_LIFECYCLE_CRITICAL_STATUSES = frozenset({"defaulted", "written_off", "overdue"})

REPAYMENT_FREQUENCIES = (
    "",
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
)

REPAYMENT_FREQUENCY_LABELS = {
    "": "Not set",
    "weekly": "Weekly",
    "biweekly": "Bi-weekly",
    "monthly": "Monthly",
    "quarterly": "Quarterly",
}

REPAYMENT_RISK_LEVELS = (
    "current",
    "watch",
    "elevated",
    "critical",
)

REPAYMENT_RISK_LABELS = {
    "current": "Current",
    "watch": "Watch list",
    "elevated": "Elevated risk",
    "critical": "Critical collections",
}

DEFAULT_REPAYMENT_RISK_LEVEL = "current"

MAX_LOAN_ACCOUNT_NUMBER_LENGTH = 32
MAX_COLLECTIONS_NOTES_LENGTH = 5000
MAX_MISSED_PAYMENT_OBSERVATIONS_LENGTH = 2000
MAX_REPAYMENT_NOTES_LENGTH = 2000
MAX_LOAN_ACCOUNT_CONTEXT_LENGTH = 1000

LOAN_ACCOUNT_AUDIT_FIELDS = (
    "loan_lifecycle_status",
    "loan_account_number",
    "issued_amount",
    "outstanding_balance",
    "repayment_progress",
    "issue_date",
    "due_date",
    "installment_amount",
    "repayment_frequency",
    "collections_notes",
    "missed_payment_observations",
    "repayment_risk_level",
)

LOAN_FIELD_ACTION_TYPES = {
    "loan_lifecycle_status": "loan_lifecycle_change",
    "loan_account_number": "loan_account_update",
    "issued_amount": "loan_terms_change",
    "outstanding_balance": "loan_balance_change",
    "repayment_progress": "loan_progress_change",
    "issue_date": "loan_terms_change",
    "due_date": "loan_terms_change",
    "installment_amount": "loan_terms_change",
    "repayment_frequency": "loan_terms_change",
    "collections_notes": "loan_collections_note",
    "missed_payment_observations": "loan_collections_observation",
    "repayment_risk_level": "loan_repayment_risk_change",
}

LOAN_STATUSES_REQUIRING_COLLECTIONS_NOTE = frozenset({"overdue", "defaulted", "written_off"})

UNDERWRITING_STATUSES_ELIGIBLE_FOR_LOAN_ACTIVATION = frozenset(
    {"approved", "conditionally_approved"}
)
