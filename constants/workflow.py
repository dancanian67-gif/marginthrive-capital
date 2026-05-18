

import re

APPLICATION_STATUSES = (
    "New applicant",
    "Collection of documentation",
    "Approval",
    "Management approval",
    "Signing agreement",
    "Final review",
    "Pending payments",
    "Loan issued",
    "Rejected",
)

KPI_PENDING_STATUSES = (
    "New applicant",
    "Collection of documentation",
    "Approval",
    "Management approval",
    "Signing agreement",
    "Final review",
)

KPI_APPROVED_STATUSES = ("Pending payments", "Loan issued")
KPI_REJECTED_STATUS = "Rejected"
KPI_HIGH_RISK_LEVELS = ("High", "Critical")

KPI_ACTIVE_PIPELINE_STATUSES = KPI_PENDING_STATUSES

KPI_CLIENT_ACTION_SUB_STATUSES = (
    "Client thinking",
    "Client to submit documentation",
    "Additional documentation",
    "Branch visit arranged",
    "Waiting for Other",
)

KPI_OPS_REVIEW_SUB_STATUS = "Margin to act"

ADMIN_FILTER_PRESETS = {
    "pipeline": "Active pipeline",
    "approved": "Approved applications",
    "rejected": "Rejected applications",
    "high_risk": "High-risk applications",
    "awaiting_client": "Awaiting client action",
    "ops_review": "Pending operational review",
    "active_loans": "Active loan accounts",
    "overdue_loans": "Overdue loan accounts",
}

ADMIN_PAGE_SIZE = 15
ADMIN_SEARCH_MAX_LENGTH = 100
OVERVIEW_LIST_LIMIT = 8
OVERVIEW_OFFICER_LIMIT = 6
ANALYTICS_OFFICER_LIMIT = 10
ANALYTICS_MAX_TREND_POINTS = 90

ANALYTICS_TIME_RANGES = {
    "today": "Today",
    "7d": "Last 7 days",
    "30d": "Last 30 days",
    "90d": "Last 90 days",
    "all": "All time",
}

DEFAULT_ANALYTICS_RANGE = "30d"

ADMIN_LIST_FILTER_KEYS = (
    "status",
    "sub_status",
    "risk_level",
    "flagged_fraud",
    "assigned_officer",
    "loan_lifecycle_status",
    "q",
    "preset",
)

APPLICATION_SUB_STATUSES = (
    "Additional documentation",
    "Client thinking",
    "Client to submit documentation",
    "Branch visit arranged",
    "Waiting for Other",
    "Margin to act",
)

DEFAULT_APPLICATION_STATUS = APPLICATION_STATUSES[0]
DEFAULT_RISK_LEVEL = "Unassigned"

APPLICATION_RISK_LEVELS = (
    "Unassigned",
    "Low",
    "Medium",
    "High",
    "Critical",
)

MAX_APPROVAL_NOTES_LENGTH = 5000
MAX_ASSIGNED_OFFICER_LENGTH = 150

OFFICER_NAME_PATTERN = re.compile(r"^[\w\s.'\-]{0,150}$", re.UNICODE)

WORKFLOW_STATUS_GROUPS = (
    ("Intake & documentation", ("New applicant", "Collection of documentation")),
    ("Approval", ("Approval", "Management approval", "Signing agreement", "Final review")),
    ("Funding", ("Pending payments", "Loan issued")),
    ("Closed", (KPI_REJECTED_STATUS,)),
)

WORKFLOW_SUB_STATUS_GROUPS = (
    ("Client action", KPI_CLIENT_ACTION_SUB_STATUSES),
    ("Operations", (KPI_OPS_REVIEW_SUB_STATUS, "Additional documentation", "Branch visit arranged", "Waiting for Other")),
)
